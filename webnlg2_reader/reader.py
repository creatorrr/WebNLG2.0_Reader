from typing import List

import os
import sys
from itertools import chain
from os import path
from collections import defaultdict

import jsonlines as jsonl
from ray.util import iter as pariter
from tqdm import tqdm
import xmltodict

num_cpus = os.cpu_count() or 4

from .utils import (
    Cleaner,
    misspelling,
    rephrase,
    rephrase_if_must,
    fix_tokenize,
    fix_template_word,
    NLP,
    shell,
    flatten_list,
    show_var,
    fwrite,
)

nlp = NLP()
cleaner = Cleaner()


def parse_xml_file(file_name):
    with open(file_name, encoding="utf-8") as f:
        content = f.read()

    structure = xmltodict.parse(content)
    return structure

class RDFFileReader:
    def __init__(self, structure, verbose=False):
        self.data = []

        self.cnt_dirty_data = 0
        self.cnt_corefs = 0

        for entry_ix, entry in enumerate(
            self._triples_from_obj(structure["benchmark"]["entries"], "entry"),
        ):
            self.entry_ix = entry["@eid"]

            triplets = [
                tuple(map(str.strip, r.split("|")))
                for r in self._triples_from_obj(entry["modifiedtripleset"], "mtriple")
            ]

            entitymaps = dict(
                [
                    tuple(map(str.strip, entitymap.split("|")))
                    for entitymap in self._triples_from_obj(
                        entry["entitymap"], "entity"
                    )
                ]
            )

            sentences = list(self.extract_sentences(entry["lex"]))

            for s_tripleset, text, template, ner2ent in sentences:
                self.data.append(
                    {
                        # 'rdfs': triplets,
                        "triples": s_tripleset,
                        "target": template,
                        "target_txt": text,
                        "ner2ent": ner2ent,
                    }
                )
        if verbose and self.cnt_dirty_data:
            show_var(["self.cnt_dirty_data"])
        if verbose and self.cnt_corefs:
            show_var(["self.cnt_corefs"])

    @staticmethod
    def _triples_from_obj(obj, t_name):
        def _triples_fix(triplets):
            if not isinstance(triplets, list):
                return [triplets]
            else:
                return [t for t in triplets]

        if not isinstance(obj, list):
            if obj is not None:
                if t_name in obj:
                    return _triples_fix(obj[t_name])
            return []
        else:
            return [_triples_fix(o[t_name]) for o in obj]

    def extract_sentences(self, lex):
        sentences = lex
        if not isinstance(sentences, list):
            sentences = [sentences]

        for s in sentences:
            if s["@comment"] == "bad":
                continue

            template = s["template"]
            text = s["text"]
            tag2ent = {
                r["@tag"]: r["@entity"]
                for r in self._triples_from_obj(s["references"], "reference")
            }
            s_tripleset_raw = [
                [
                    tuple(map(str.strip, r.split("|")))
                    for r in self._triples_from_obj(s_triples, "striple")
                ]
                for s_triples in self._triples_from_obj(
                    s["sortedtripleset"], "sentence"
                )
                if s_triples
            ]
            fixed = self.fix_document(s_tripleset_raw, template, text, tag2ent)
            if fixed is None:
                continue
            s_tripleset, template, text, tag2ent = fixed

            if len(s_tripleset) == 1:
                template = [template]
                text = [text]
            else:
                template = nlp.sent_tokenize(template)
                text = nlp.sent_tokenize(text)
                text = fix_tokenize(text)

            if len({len(template), len(text), len(s_tripleset)}) != 1:
                # import pdb;
                # pdb.set_trace()
                self.cnt_dirty_data += 1
                continue

            for s_t, tex, tem in zip(s_tripleset, text, template):

                new_s_t, tem, uniq_tag2ent = self.fix_sentence(s_t, tem, tag2ent)
                if not (new_s_t and tem and tex and uniq_tag2ent):
                    self.cnt_corefs += 1
                    # import pdb;pdb.set_trace()
                    continue

                yield new_s_t, tex, tem, uniq_tag2ent

    def fix_document(self, s_tripleset_raw, template, text, tag2ent):
        # check template
        template = (
            " ".join(
                [
                    fix_template_word[word] if word in fix_template_word else word
                    for word in template.split()
                ]
            )
            if template
            else template
        )

        # tokenization
        text = nlp.word_tokenize(text)
        template = nlp.word_tokenize(template)

        # clean s_tripleset
        s_tripleset = [s for s in s_tripleset_raw if s]
        self.cnt_dirty_data += len(s_tripleset_raw) - len(s_tripleset)

        if (not tag2ent) or (not s_tripleset):
            self.cnt_dirty_data += not tag2ent
            return None

        # fix this case "same entity has different ners BRIDGE-1 PATIENT-1"
        ent2tags = defaultdict(list)
        for tag, ent in tag2ent.items():
            ent2tags[ent] += [tag]
        tag2uniq_tag = {}
        for ent, tags in ent2tags.items():
            for tag in tags:
                tag2uniq_tag[tag] = tags[0]
        uniq_tag2ent = {
            tag: ent
            for tag, ent in tag2ent.items()
            if tag in list(tag2uniq_tag.values())
        }
        for tag, uniq_tag in tag2uniq_tag.items():
            template = template.replace(tag, uniq_tag)

        assert uniq_tag2ent
        ent2uniq_tag = {v: k for k, v in uniq_tag2ent.items()}
        assert len(ent2uniq_tag) == len(uniq_tag2ent)

        # clean out extra quotes around entity names
        uniq_tag2ent = {k: v.strip('"') for k, v in uniq_tag2ent.items()}
        try:
            s_tripleset = [
                [
                    (subj.strip('"'), predi, obj.strip('"'))
                    for subj, predi, obj in s_triples
                ]
                for s_triples in s_tripleset
            ]
        except:
            import pdb

            pdb.set_trace()

        # replaces '-' with '_' only in entity types
        tags = set(uniq_tag2ent.keys())
        for tag in tags:
            template = template.replace(tag, tag.replace("-", "_"))
        template = template.replace("BRIDGE-", "BRIDGE_")
        template = template.replace("AGENT-", "AGENT_")
        template = template.replace("PATIENT-", "PATIENT_")
        uniq_tag2ent = {k.replace("-", "_"): v for k, v in uniq_tag2ent.items()}

        return s_tripleset, template, text, uniq_tag2ent

    def fix_sentence(self, s_tripleset, template, tag2ent):
        ent2tags = {v: k for k, v in tag2ent.items()}

        # s_tripleset must meet "head && tail are in template && tag2ent"
        bad_triples = set()
        for triple_ix, triple in enumerate(s_tripleset):
            for ent in [triple[0], triple[-1]]:
                if ent in ent2tags:
                    if ent2tags[ent] not in template:
                        bad_triples.add(triple_ix)
                        continue
                else:
                    bad_triples.add(triple_ix)
                    continue
        s_tripleset = [
            triple
            for triple_ix, triple in enumerate(s_tripleset)
            if triple_ix not in bad_triples
        ]

        # tag2ent are entities only in triple_entities
        triple_entities = set(
            flatten_list([(triple[0], triple[-1]) for triple in s_tripleset])
        )
        tag2tri_ent = {k: v for k, v in tag2ent.items() if v in triple_entities}

        # templates only have triple_entities
        for tag, ent in tag2ent.items():
            if ent not in triple_entities:
                ent = ent.replace("_", " ")
                template = template.replace(tag, ent)

        if {
            word
            for word in template.split()
            if "AGENT" in word or "BRIDGE" in word or "PATIENT" in word
        } != set(tag2tri_ent.keys()):
            self.cnt_corefs += 1
        assert set(tag2tri_ent.values()) == triple_entities

        return s_tripleset, template, tag2tri_ent


def process_data(data_set_type: str, parallel=True):
    files = recurse_files(path.join("./data/webnlg", "raw", data_set_type))
    xml_objs = [parse_xml_file(f) for f in files]

    entries = []
    if not parallel:
        print(f"[Info] Processing data...")

        chunks = [RDFFileReader(x).data for x in xml_objs]
        entries = flatten_list(chunks)

    else:
        num_shards: int = num_cpus if parallel else 1
        print(f"[Info] Processing data in {num_shards} shards...")

        iterator = (
            pariter.from_items(xml_objs[0:5], num_shards=num_shards)
            # .for_each(lambda f: cleaner.clean)
            .for_each(lambda xmldata: RDFFileReader(xmldata).data)
            .flatten()
        )

        entries = iterator.gather_async()

    return tqdm(entries, desc="WebNLG", unit="entry")

def recurse_files(folder: str) -> List[str]:
    if path.isdir(folder):
        return flatten_list(
            [
                recurse_files(folder + "/" + f)
                for f in os.listdir(folder)
                if not f.startswith(".")
            ]
        )
    return [folder]


def save_data(data, data_set_type):
    data_set_type = "valid" if data_set_type == "dev" else data_set_type
    save_f = path.join("./data/webnlg", data_set_type + ".jsonl")

    total = 0
    with jsonl.open(save_f, "w") as f:
        for row in data:
            total += 1
            f.write(row)

    print(f"[Info] Saved {total} entries into {save_f}")


def download(
    repo: str = "ThiagoCF05/webnlg", revision: str = "711a8ca", version: str = "v1.6"
) -> None:
    cmd = [
        f"rm -rf data/webnlg 2>/dev/null \n",
        f"mkdir -p data/webnlg \n",
        f"git clone --depth 1 https://github.com/{repo}.git data_webnlg\n",
        f"cd data_webnlg; git checkout {revision}; cd .. \n",
        f"cp -a data_webnlg/data/{version}/en/ data/webnlg/raw\n",
        f"rm -rf data_webnlg\n",
    ]

    print("[Info] Downloading enriched WebNLG data...")

    for x in cmd:
        print(f"> {x}")
        shell(x)
