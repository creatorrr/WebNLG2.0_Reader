# -*- coding: utf-8 -*-
from typing import Any, List, Tuple, Dict, Callable, Union

from itertools import chain, permutations
import json
import os
import re
from subprocess import PIPE, Popen, STDOUT
import sys

import spacy

# Ensure spacy model is installed
try:
    import en_core_web_md
except ImportError:
    spacy.cli.download(model="en_core_web_md")

from .patterns.constants import SPLITABLES
from .patterns.filter_dic_raw import filter_dic_raw
from .patterns.fix_template_word import fix_template_word
from .patterns.fix_tokenize import fix_tokenize
from .patterns.misc import misspelling, rephrasing, rephrasing_must


class DataReader:
    def __init__(
        self,
        data: List[dict],
        rephrase: Tuple[Callable, Callable],
        misspelling: Dict[str, str] = None,
    ):
        self.data = data
        self.misspelling = misspelling
        self.rephrase = rephrase

    def fix_spelling(self):
        if not self.misspelling:
            return self

        regex_splittable = "(\\" + "|\\".join(SPLITABLES) + ".)"

        for misspelling, fix in self.misspelling.items():
            source = regex_splittable + misspelling + regex_splittable
            target = "\1" + fix + "\2"

            self.data = [d.set_text(re.sub(source, target, d.text)) for d in self.data]
        return self


class Cleaner:
    def __init__(self, verbose: bool = False) -> None:
        self.fname_ends = [k[0] for k in self.filter_dic]
        if verbose:
            keys = set(self.filter_dic.keys())
            with open("temp.txt") as f:
                data = [tuple(json.loads(line)) for line in f if line]

            # if set(data) != set(keys):
            #     set(keys) - set(data)

    def clean(self, filename: str) -> None:
        fname_end = "/".join(filename.rsplit("/", 3)[1:])

        if fname_end not in self.fname_ends:
            return

        with open(filename, encoding="utf-8", errors="ignore") as f:
            lines = []
            content = f.readlines()
            for line_ix, line in enumerate(content):
                line = self.filter_line(fname_end, line_ix, line)
                if line:
                    lines.append(line)
        if lines != content:
            fwrite("".join(lines), filename)

    def filter_line(self, fname_end, line_ix, line):
        line = self.line_fix(line)

        text = line.strip()
        key = (fname_end, line_ix, text)
        if key in self.filter_dic:
            # fwrite(json.dumps(key) + '\n', 'temp.txt', mode='a')
            new_text = self.filter_dic[key]
            if not new_text:
                return False
            line = line.replace(text, new_text)

        return line

    @staticmethod
    def line_fix(line):
        line = line.replace(
            " (abbrv. Acta Palaeontol. Pol)", " (abbrv Acta Palaeontol Pol)"
        )
        return line

    @property
    def filter_dic(self) -> Dict[Tuple[str, int, str], Union[bool, str]]:
        return filter_dic_raw


class NLP:
    def __init__(self):

        self.nlp = spacy.load("en_core_web_md", disable=["ner", "parser", "tagger"])
        self.nlp.add_pipe(self.nlp.create_pipe("sentencizer"))

    def sent_tokenize(self, text):
        doc = self.nlp(text)
        sentences = [sent.string.strip() for sent in doc.sents]
        return sentences

    def word_tokenize(self, text, lower=False):  # create a tokenizer function
        if text is None:
            return text
        text = " ".join(text.split())
        if lower:
            text = text.lower()
        toks = [tok.text for tok in self.nlp.tokenizer(text)]
        return " ".join(toks)


def show_var(expression, joiner="\n"):
    """
    Prints out the name and value of variables.
    Eg. if a variable with name `num` and value `1`,
    it will print "num: 1\n"

    Parameters
    ----------
    expression: ``List[str]``, required
        A list of varible names string.

    Returns
    ----------
        None
    """

    var_output = []

    for var_str in expression:
        frame = sys._getframe(1)
        value = eval(var_str, frame.f_globals, frame.f_locals)

        if " object at " in repr(value):
            value = vars(value)
            value = json.dumps(value, indent=2)
            var_output += ["{}: {}".format(var_str, value)]
        else:
            var_output += ["{}: {}".format(var_str, repr(value))]

    if joiner != "\n":
        output = "[Info] {}".format(joiner.join(var_output))
    else:
        output = joiner.join(var_output)
    print(output)
    return output


def fwrite(new_doc, path, mode="w", no_overwrite=False):
    if not path:
        print("[Info] Path does not exist in fwrite():", str(path))
        return
    if no_overwrite and os.path.isfile(path):
        print("[Error] pls choose whether to continue, as file already exists:", path)
        import pdb

        pdb.set_trace()
        return
    with open(path, mode) as f:
        f.write(new_doc)


def shell(
    cmd: str, working_directory: str = ".", stdout: bool = False, stderr: bool = False
) -> Tuple[bytes, bytes]:
    subp = Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT, cwd=working_directory)
    subp_stdout, subp_stderr = subp.communicate()

    if stdout and subp_stdout:
        print("[stdout]", subp_stdout, "[end]")
    if stderr and subp_stderr:
        print("[stderr]", subp_stderr, "[end]")

    return subp_stdout, subp_stderr


def flatten_list(nested_list: List[List[Any]]) -> List[Any]:

    return list(chain.from_iterable(nested_list))


def rephrase(entity):
    phrasings = {entity}

    for s, rephs in rephrasing.items():
        for p in [p for p in set(phrasings) if s in p]:
            for r in rephs:
                phrasings.add(p.replace(s, r))

    # Allow rephrase "a/b/.../z" -> every permutation
    for p in set(phrasings):
        for permutation in permutations(p.split("/")):
            phrasings.add("/".join(permutation))

    # Allow rephrase "number (unit)" -> "number unit", "number unit-short"
    for p in set(phrasings):
        match = re.match(r"^(-?(\d+|\d{1,3}(,\d{3})*)(\.\d+)?)( (\((.*?)\)))?$", p)
        if match:
            groups = match.groups()
            number = float(groups[0])
            unit = groups[6]

            number_phrasing = [str(number), str("{:,}".format(number))]
            if round(number) == number:
                number_phrasing.append(str(round(number)))
                number_phrasing.append(str("{:,}".format(round(number))))

            if unit:
                couple = None
                words = [unit]

                if unit == "metres":
                    couple = "m"
                    words = [unit, "meters"]
                elif unit == "millimetres":
                    couple = "mm"
                elif unit == "centimetres":
                    couple = "cm"
                elif unit == "kilometres":
                    couple = "km"
                elif unit == "kilograms":
                    couple = "kg"
                elif unit == "litres":
                    couple = "l"
                elif unit == "inches":
                    couple = "''"
                elif unit in ["degreecelsius", "degreeklsius"]:
                    words = ["degrees celsius"]
                elif unit == "grampercubiccentimetres":
                    words = ["grams per cubic centimetre"]
                elif unit == "kilometreperseconds":
                    words = [
                        "kilometres per second",
                        "km/s",
                        "km/sec",
                        "km per second",
                        "km per sec",
                    ]
                elif unit in ["squarekilometres", "square kilometres"]:
                    words = ["square kilometres", "sq km"]
                elif unit == "cubiccentimetres":
                    couple = "cc"
                    words = ["cubic centimetres"]
                elif unit in [
                    "cubic inches",
                    "days",
                    "tonnes",
                    "square metres",
                    "inhabitants per square kilometre",
                    "kelvins",
                ]:
                    pass
                else:
                    raise ValueError(unit + " is unknown")

                for np in number_phrasing:
                    if couple:
                        phrasings.add(np + " " + couple)
                        phrasings.add(np + couple)
                    for word in words:
                        phrasings.add(np + " " + word)
            else:
                for np in number_phrasing:
                    phrasings.add(np)

    # Allow rephrase "word1 (word2)" -> "word2 word1"
    for p in set(phrasings):
        match = re.match(r"^(.* ?) \((.* ?)\)$", p)
        if match:
            groups = match.groups()
            s = groups[0]
            m = groups[1]
            phrasings.add(s + " " + m)
            phrasings.add(m + " " + s)

    return set(phrasings)


def rephrase_if_must(entity):
    phrasings = {entity}

    for s, rephs in rephrasing_must.items():
        for p in [p for p in set(phrasings) if s in p]:
            for r in rephs:
                phrasings.add(p.replace(s, r))

    # Allow removing parenthesis "word1 (word2)" -> "word1"
    for p in set(phrasings):
        match = re.match(r"^(.* ?) \((.* ?)\)$", p)
        if match:
            groups = match.groups()
            phrasings.add(groups[0])

    # Allow rephrase "word1 (word2) word3?" -> "word1( word3)"
    for p in set(phrasings):
        match = re.match(r"^(.*?) \((.*?)\)( .*)?$", p)
        if match:
            groups = match.groups()
            s = groups[0]
            m = groups[2]
            phrasings.add(s + " " + m if m else "")

    # Allow rephrase "a b ... z" -> every permutation
    # for p in set(phrasings):
    #     for permutation in permutations(p.split(" ")):
    #         phrasings.add(" ".join(permutation))

    phrasings = set(phrasings)
    if "" in phrasings:
        phrasings.remove("")
    return phrasings
