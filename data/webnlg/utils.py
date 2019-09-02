# -*- coding: utf-8 -*-
from __future__ import division, unicode_literals, print_function

import itertools
import re
import json

from enum import Enum
from typing import List, Tuple, Dict, Callable

import sys
import os.path

try:
    import spacy
except ImportError:
    os.system('pip install spacy')
    os.system('python -m spacy download en')
    import spacy


class DataSetType(Enum):
    DEV = "dev"
    TEST = "test"
    TRAIN = "train"


misspelling = {
    "accademiz": "academia",
    "withreference": "with reference",
    "thememorial": "the memorial",
    "unreleated": "unrelated",
    "varation": "variation",
    "variatons": "variations",
    "youthclub": "youth club",
    "oprated": "operated",
    "originaly": "originally",
    "origintes": "originates",
    "poacea": "poaceae",
    "posgraduayed": "postgraduate",
    "prevously": "previously",
    "publshed": "published",
    "punlished": "published",
    "recor": "record",
    "relgiion": "religion",
    "runwiay": "runway",
    "sequeled": "runway",
    "sppoken": "spoken",
    "studiies": "studies",
    "sytle": "style",
    "tboh": "both",
    "whic": "which",
    "identfier": "identifier",
    "idenitifier": "identifier",
    "igredient": "ingredients",
    "ingridient": "ingredients",
    "inclusdes": "includes",
    "indain": "indian",
    "leaderr": "leader",
    "legue": "league",
    "lenght": "length",
    "loaction": "location",
    "locaated": "located",
    "locatedd": "located",
    "locationa": "location",
    "managerof": "manager of",
    "manhattern": "manhattan",
    "memberrs": "members",
    "menbers": "members",
    "meteres": "metres",
    "numbere": "number",
    "numberr": "number",
    "notablework": "notable work",
    "7and": "7 and",
    "abbreivated": "abbreviated",
    "abreviated": "abbreviated",
    "abreviation": "abbreviation",
    "addres": "address",
    "abbreviatedform": "abbreviated form",
    "aerbaijan": "azerbaijan",
    "azerbijan": "azerbaijan",
    "affilaited": "affiliated",
    "affliate": "affiliate",
    "aircfrafts": "aircraft",
    "aircrafts": "aircraft",
    "aircarft": "aircraft",
    "airpor": "airport",
    "in augurated": "inaugurated",
    "inagurated": "inaugurated",
    "inaugrated": "inaugurated",
    "ausitin": "austin",
    "coccer": "soccer",
    "comanded": "commanded",
    "constructionof": "construction of",
    "counrty": "country",
    "countyof": "county of",
    "creater": "creator",
    "currecncy": "currency",
    "denonym": "demonym",
    "discipine": "discipline",
    "engish": "english",
    "establishedin": "established in",
    "ethinic": "ethnic",
    "ethiopa": "ethiopia",
    "ethipoia": "ethiopia",
    "eceived": "received",
    "ffiliated": "affiliated",
    "fullname": "full name",
    "grop": "group"
}

rephrasing = {
    # Add an acronym database
    "united states": ["u.s.", "u.s.a.", "us", "usa", "america", "american"],
    "united kingdom": ["u.k.", "uk"],
    "united states air force": ["usaf", "u.s.a.f"],
    "new york": ["ny", "n.y."],
    "new jersey": ["nj", "n.j."],
    "f.c.": ["fc"],
    "submarine": ["sub"],
    "world war ii": ["ww ii", "second world war"],
    "world war i": ["ww i", "first world war"],

    "greece": ["greek"],
    "canada": ["canadian"],
    "italy": ["italian"],
    "america": ["american"],
    "india": ["indian"],
    "singing": ["sings"],
    "conservative party (uk)": ["tories"],
    "ethiopia": ["ethiopian"],
}

rephrasing_must = {
    # Add a rephrasing database
    " language": "",
    " music": "",
    "kingdom of ": "",
    "new york city": "new york",
    "secretary of state of vermont": "secretary of vermont"
}


def rephrase(entity):
    phrasings = {entity}

    for s, rephs in rephrasing.items():
        for p in filter(lambda p: s in p, set(phrasings)):
            for r in rephs:
                phrasings.add(p.replace(s, r))

    # Allow rephrase "a/b/.../z" -> every permutation
    for p in set(phrasings):
        for permutation in itertools.permutations(p.split("/")):
            phrasings.add("/".join(permutation))

    # Allow rephrase "number (unit)" -> "number unit", "number unit-short"
    for p in set(phrasings):
        match = re.match("^(-?(\d+|\d{1,3}(,\d{3})*)(\.\d+)?)( (\((.*?)\)))?$",
                         p)
        if match:
            groups = match.groups()
            number = float(groups[0])
            unit = groups[6]

            number_phrasing = [
                str(number),
                str("{:,}".format(number))
            ]
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
                    words = ["kilometres per second", "km/s", "km/sec",
                             "km per second", "km per sec"]
                elif unit in ["squarekilometres", "square kilometres"]:
                    words = ["square kilometres", "sq km"]
                elif unit == "cubiccentimetres":
                    couple = "cc"
                    words = ["cubic centimetres"]
                elif unit in ["cubic inches", "days", "tonnes", "square metres",
                              "inhabitants per square kilometre", "kelvins"]:
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
        match = re.match("^(.* ?) \((.* ?)\)$", p)
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
        for p in filter(lambda p: s in p, set(phrasings)):
            for r in rephs:
                phrasings.add(p.replace(s, r))

    # Allow removing parenthesis "word1 (word2)" -> "word1"
    for p in set(phrasings):
        match = re.match("^(.* ?) \((.* ?)\)$", p)
        if match:
            groups = match.groups()
            phrasings.add(groups[0])

    # Allow rephrase "word1 (word2) word3?" -> "word1( word3)"
    for p in set(phrasings):
        match = re.match("^(.*?) \((.*?)\)( .*)?$", p)
        if match:
            groups = match.groups()
            s = groups[0]
            m = groups[2]
            phrasings.add(s + " " + m if m else "")

    # Allow rephrase "a b ... z" -> every permutation
    # for p in set(phrasings):
    #     for permutation in itertools.permutations(p.split(" ")):
    #         phrasings.add(" ".join(permutation))

    phrasings = set(phrasings)
    if "" in phrasings:
        phrasings.remove("")
    return phrasings


class Cleaner():
    def __init__(self):
        pass
        # for filename in filenames:
        #     self.clean(filename)

    def clean(self, filename):
        fname_end = '/'.join(filename.rsplit('/', 3)[1:])

        with open(filename, encoding="utf-8", errors='ignore') as f:
            lines = []
            content = f.readlines()
            for line_ix, line in enumerate(content):
                line = self.filter(fname_end, line_ix,
                                   line)
                if line: lines.append(line)
        if lines != content:
            fwrite(''.join(lines), filename)

    def filter(self, fname_end, line_ix, line):
        filter_dic = {
            ('train/1triples/SportsTeam.xml', 1811,
             '<sentence ID="2"/>'): False,
            ('train/1triples/SportsTeam.xml', 1817,
             '<text>The full name of the A.F.C. Fylde is &quot;Association Football Club Fylde.&quot;.</text>'):
                '<text>The full name of the A.F.C. Fylde is &quot;Association Football Club Fylde.&quot;</text>',
            ('train/1triples/SportsTeam.xml', 1818,
             '<template>The full name of AGENT-1 is `` PATIENT-1 . '' .</template>'):
                '<template>The full name of AGENT-1 is `` PATIENT-1 . ''</template>',
            ('train/1triples/SportsTeam.xml', 1819,
             "<lexicalization>DT[form=defined] the full name of AGENT-1 VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be `` PATIENT-1 . '' .</lexicalization>"):
                "<lexicalization>DT[form=defined] the full name of AGENT-1 VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be `` PATIENT-1 . ''</lexicalization>",
            ('train/1triples/SportsTeam.xml', 7190,
             '<sentence ID="1"/>'): False,
            ('train/1triples/SportsTeam.xml', 7191,
             '<sentence ID="2">'): '<sentence ID="1">',

            ('train/1triples/Airport.xml', 1298, '<sentence ID="1"/>'): False,
            ('train/1triples/Airport.xml', 1299,
             '<sentence ID="2">'): '<sentence ID="1">',
            ('train/1triples/Airport.xml', 2225, '<sentence ID="1"/>'): False,
            ('train/1triples/Airport.xml', 2226,
             '<sentence ID="2">'): '<sentence ID="1">',

            (
                'train/1triples/University.xml', 1153,
                '<sentence ID="2"/>'): False,

            ('train/1triples/Building.xml', 1966, '<sentence ID="2"/>'): False,
            ('train/1triples/Building.xml', 1972,
             '<text>The 3Arena is located at &quot;North Wall Quay.&quot;.</text>'): '<text>The 3Arena is located at &quot;North Wall Quay.&quot;</text>',
            ('train/1triples/Building.xml', 1973,
             '<template>AGENT-1 is located at `` PATIENT-1 . '' .</template>'): '<template>AGENT-1 is located at `` PATIENT-1 . ''</template>',

            ('train/5triples/Monument.xml', 3546,
             '<text>The 14th New Jersey Volunteer Infantry Monument by the National Park Service, located in the Monocacy National Battlefield was established in 1907-07-11.The Monocacy National Battlefield is located in Frederick County, Maryland and the nearest city to it is Frederick, Maryland.</text>'):
                '<text>The 14th New Jersey Volunteer Infantry Monument by the National Park Service, located in the Monocacy National Battlefield was established in 1907-07-11. The Monocacy National Battlefield is located in Frederick County, Maryland and the nearest city to it is Frederick, Maryland.</text>',
            ('train/5triples/Astronaut.xml', 6697, '<sentence ID="3"/>'): False,
            ('train/5triples/Astronaut.xml', 1937, '<sentence ID="3"/>'): False,
            ('train/5triples/Astronaut.xml', 1938,
             '<sentence ID="4">'): '<sentence ID="3">',

            ('train/5triples/Building.xml', 133,
             '<text>John Madin was the architect of the building located at 103 Colmore Row .The building was completed in 1976.</text>'): '<text>John Madin was the architect of the building located at 103 Colmore Row. The building was completed in 1976.</text>',
            ('train/5triples/Building.xml', 1422, '<sentence ID="3"/>'): False,
            ('train/5triples/Building.xml', 5741, '<sentence ID="3"/>'): False,
            ('train/5triples/Building.xml', 8042, '<sentence ID="4"/>'): False,

            ('train/5triples/University.xml', 81,
             '<text>The rector of the 1 Decembrie 1918 Universitie is Breaz Valer Daniel.. The university, which is nicknamed Uab, is in Alba Julia in Romania.</text>'): '<text>The rector of the 1 Decembrie 1918 Universitie is Breaz Valer Daniel. The university, which is nicknamed Uab, is in Alba Julia in Romania.</text>',
            ('train/5triples/University.xml', 674,
             '<text>Mario Botta is the dean of the Accademia di Architettura di Mendrisio in the Swiss city of Mendrisio.It was established in 1996. The leader of Switzerland is Johann Schneider -Ammann.</text>'):
                '<text>Mario Botta is the dean of the Accademia di Architettura di Mendrisio in the Swiss city of Mendrisio, which was established in 1996. The leader of Switzerland is Johann Schneider -Ammann.</text>',
            ('train/5triples/University.xml', 675,
             '<template>PATIENT-1 is the dean of AGENT-1 in the Swiss city of PATIENT-3 was established in PATIENT-2 . The leader of BRIDGE-1 is PATIENT-4 .</template>'):
                '<template>PATIENT-1 is the dean of AGENT-1 in the Swiss city of PATIENT-3 , which was established in PATIENT-2 . The leader of BRIDGE-1 is PATIENT-4 .</template>',

            ('train/5triples/Airport.xml', 4116, '</sentence>'): False,
            ('train/5triples/Airport.xml', 4117, '<sentence ID="2">'): False,
            ('train/5triples/Airport.xml', 4120,
             '<sentence ID="3">'): '<sentence ID="2">',
            ('train/5triples/Airport.xml', 8007, '<sentence ID="2"/>'): False,
            ('train/5triples/Airport.xml', 9810, '</sentence>'): False,
            ('train/5triples/Airport.xml', 9811, '<sentence ID="3">'): False,
            ('train/5triples/Airport.xml', 14745, '<sentence ID="3"/>'): False,
            ('train/5triples/Airport.xml', 16832,
             '<text>Al-Taqaddum Air base serves the city of Fallujah in Iraq. Haider al-Abadi is the prime minister of the country and the president is called Fuad Masum(a kurdish politician).Kurdish is one of the spoken languages of Iraq.</text>'): '<text>Al-Taqaddum Air base serves the city of Fallujah in Iraq. Haider al-Abadi is the prime minister of the country and the president is called Fuad Masum(a kurdish politician). Kurdish is one of the spoken languages of Iraq.</text>',

            ('train/5triples/Food.xml', 8131, '<sentence ID="2"/>'): False,
            ('train/5triples/Food.xml', 8132,
             '<sentence ID="3">'): '<sentence ID="2">',
            ('train/5triples/Food.xml', 8143,
             '<text>Bakewell pudding (bakewell tart) is a dessert from the Derbyshire Dales region and can be served warm or cold.. The main ingredients include ground almond, jam, butter and eggs.</text>'): '<text>Bakewell pudding (bakewell tart) is a dessert from the Derbyshire Dales region and can be served warm or cold. The main ingredients include ground almond, jam, butter and eggs.</text>',
            ('train/5triples/Food.xml', 8144,
             '<template>AGENT-1 (PATIENT-2) is PATIENT-4 from the PATIENT-1 region and can be served PATIENT-3 . . The main ingredients include PATIENT-5 .</template>'): '<template>AGENT-1 (PATIENT-2) is PATIENT-4 from the PATIENT-1 region and can be served PATIENT-3 . The main ingredients include PATIENT-5 .</template>',
            ('train/5triples/Food.xml', 10537,
             "<text>Batagor, Siomay &amp; shumai come from Indonesia .Batagor &amp; Siomay are variations of the same dish &amp; Batagor is a variation of shumai. Batagor's main ingredients are fried fish dumplings with tofu &amp; vegetables in peanut sauce.</text>"): "<text>Batagor, Siomay &amp; shumai come from Indonesia . Batagor &amp; Siomay are variations of the same dish &amp; Batagor is a variation of shumai. Batagor's main ingredients are fried fish dumplings with tofu &amp; vegetables in peanut sauce.</text>",

            ('train/6triples/Monument.xml', 3657, '<sentence ID="1"/>'): False,
            ('train/6triples/Monument.xml', 3658,
             '<sentence ID="2">'): '<sentence ID="1">',
            ('train/6triples/Monument.xml', 3666, '<sentence ID="3"/>'): False,

            ('train/6triples/Monument.xml', 3676,
             '<text>The President of Turkey is Ahmet Davutoglu. The capital is Ankara, but it is in Izmir that the bronze @ Ataturk monument is located and was inaugurated on 27 July 1932. .</text>'):
                '<text>The President of Turkey is Ahmet Davutoglu. The capital is Ankara, but it is in Izmir that the bronze @ Ataturk monument is located and was inaugurated on 27 July 1932.</text>',
            ('train/6triples/Monument.xml', 3677,
             '<template>PATIENT-1 is PATIENT-2 . The capital is PATIENT-3 , but it is in BRIDGE-1 that PATIENT-4 @ AGENT-1 is located and was inaugurated on PATIENT-5 . .</template>'):
                '<template>PATIENT-1 is PATIENT-2 . The capital is PATIENT-3 , but it is in BRIDGE-1 that PATIENT-4 @ AGENT-1 is located and was inaugurated on PATIENT-5 .</template>',
            ('train/6triples/Monument.xml', 3678,
             '<lexicalization>PATIENT-1 VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be PATIENT-2 . DT[form=defined] the capital VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be PATIENT-3 , but it VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be in BRIDGE-1 that PATIENT-4 AGENT-1 VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be located and VP[aspect=simple,tense=past,voice=passive,person=null,number=singular] inaugurate on PATIENT-5 . .</lexicalization>'):
                '<lexicalization>PATIENT-1 VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be PATIENT-2 . DT[form=defined] the capital VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be PATIENT-3 , but it VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be in BRIDGE-1 that PATIENT-4 AGENT-1 VP[aspect=simple,tense=present,voice=active,person=3rd,number=singular] be located and VP[aspect=simple,tense=past,voice=passive,person=null,number=singular] inaugurate on PATIENT-5 .</lexicalization>',

            ('train/6triples/Astronaut.xml', 6959,
             '<text>Born on the 17th of October 1933 @ William Anders started working for NASA in 1963 .He was a crew member on the NASA operated Apollo 8 mission along with backup pilot Buzz Aldrin and Frank Borman.</text>'):
                '<text>Born on the 17th of October 1933 @ William Anders started working for NASA in 1963. He was a crew member on the NASA operated Apollo 8 mission along with backup pilot Buzz Aldrin and Frank Borman.</text>',
            ('train/6triples/Astronaut.xml', 7190,
             '<text>William ANders was born on 1933-10-17 in British Hong Kong. He received a M.S. from his alma Mater, AFIT in 1962. He was a fighter pilot and retired on September 1st. 1969.</text>'):
                '<text>William ANders was born on 1933-10-17 in British Hong Kong. He received a M.S. from his alma Mater, AFIT in 1962. He was a fighter pilot and retired on September 1st, 1969.</text>',

            ('train/6triples/University.xml', 6466,
             '<sentence ID="2"/>'): False,
            ('train/6triples/University.xml', 6467,
             '<sentence ID="3">'): '<sentence ID="2">',
            ('train/6triples/University.xml', 6613,
             '<sentence ID="4"/>'): False,
            # ('train/6triples/Astronaut.xml', 47,
            #  '<text>United States @ test pilot @ Alan Bean was born in Wheeler, Texas. In 1955, he graduated from UT Austin with a B.S. Chosen by NASA in 1963, he managed a total space time of 100305.0 minutes.</text>'):
            #     '<text>United States @ test pilot @ Alan Bean was born in Wheeler, Texas. In 1955, he graduated from UT Austin with a BS. Chosen by NASA in 1963, he managed a total space time of 100305.0 minutes.</text>',
            # ('train/6triples/Astronaut.xml', 129,
            #  '<text>Alan Bean was born in Wheeler, Texas, the United States. He was a member of Apollo 12 and also served as a test pilot. He graduated from UT Austin 1955 with a B.S. and is now retired.</text>'):
            #     '<text>Alan Bean was born in Wheeler, Texas, the United States. He was a member of Apollo 12 and also served as a test pilot. He graduated from UT Austin 1955 with a BS and is now retired.</text>',
            # ('train/6triples/Astronaut.xml', 212,
            #  '<text>American @ test pilot @ Alan Bean was born in Wheeler, Texas. He graduated from UT Austin with a B.S. in 1955. He served as a crew member of Apollo 12 and spent a total of 100305 minutes in space.</text>'):
            #     '<text>American @ test pilot @ Alan Bean was born in Wheeler, Texas. He graduated from UT Austin with a BS in 1955. He served as a crew member of Apollo 12 and spent a total of 100305 minutes in space.</text>',
            # ('train/6triples/Astronaut.xml', 240,
            #  '<text>American @ Alan Bean was born in Wheeler, Texas. He performs as a test pilot, graduated from UT Austin in 1955 with a B.S. was a part of the crew of Apollo 12 and his time in space was 100305.0 minutes.</text>'):
            #     '<text>American @ Alan Bean was born in Wheeler, Texas. He performs as a test pilot, graduated from UT Austin in 1955 with a BS was a part of the crew of Apollo 12 and his time in space was 100305.0 minutes.</text>',
            # ('train/6triples/Astronaut.xml', 348,
            #  '<text>Alan Bean was an American @ test pilot selected by NASA to part of the Apollo 12 crew in 1963. His Alma Mater is UT Austin, where he received as B.S. in 1955.</text>'):
            #     '<text>Alan Bean was an American @ test pilot selected by NASA to part of the Apollo 12 crew in 1963. His Alma Mater is UT Austin, where he received as BS in 1955.</text>'
            ('dev/5triples/Food.xml', 647,
             '<lex comment="good" lid="Id1">'): '<lex comment="bad" lid="Id1">',

            ('dev/5triples/Food.xml', 653,
             '<lex comment="good" lid="Id2">'): '<lex comment="bad" lid="Id2">',

            ('dev/5triples/Food.xml', 659,
             '<lex comment="good" lid="Id3">'): '<lex comment="bad" lid="Id3">',

            ('test/5triples/MeanOfTransportation.xml', 137,
             '<text>AIDAstella was built by Meyer Werft and is operated by AIDA Cruise Line. The AIDAstella has a beam of 32.2 m, is 253260.0 millimetres in length and has a beam of 32.2 m.</text>'):
                '<text>AIDAstella was built by Meyer Werft. The AIDAstella has a beam of 32.2 m, is 253260.0 millimetres in length and has a beam of 32.2 m.</text>',
            ('test/5triples/MeanOfTransportation.xml', 138,
             '<template>AGENT-1 was built by PATIENT-4 and is operated by BRIDGE-1 . AGENT-1 has a beam of PATIENT-2 , is PATIENT-5 in length and has a beam of PATIENT-2 .</template>'):
                '<template>AGENT-1 was built by PATIENT-4 . AGENT-1 has a beam of PATIENT-2 , is PATIENT-5 in length and has a beam of PATIENT-2 .</template>',

            ('test/4triples/CelestialBody.xml', 34,
             '<text>The epoch of (19255) 1994 VK8 is on 31 December 2006. It has an orbital period of 8788850000.0, a periapsis of 6155910000000.0 and an apoapsis of 6603633000.0 km.</text>'):
                '<text>The epoch of (19255) 1994 VK8 is on 31 December 2006. It has an orbital period of 8788850000.0 and a periapsis of 6155910000000.0 .</text>',
            ('test/4triples/CelestialBody.xml', 35,
             '<template>The epoch of AGENT-1 is on PATIENT-1 . AGENT-1 has an orbital period of PATIENT-2 , a periapsis of PATIENT-3 and an apoapsis of PATIENT-5 .</template>'):
                '<template>The epoch of AGENT-1 is on PATIENT-1 . AGENT-1 has an orbital period of PATIENT-2 and a periapsis of PATIENT-3 .</template>',
            ('test/4triples/MeanOfTransportation.xml', 293,
             '<text>Costa Crociere is the owner of the AIDAstella which is 25326.0 millimetres long. It was built by Meyer Werft and operated by AIDA Cruise Line.</text>'):
                '<text>Costa Crociere is the owner of the AIDAstella which is 25326.0 millimetres long. It was built by Meyer Werft .</text>',
            ('test/4triples/MeanOfTransportation.xml', 294,
             '<template>PATIENT-4 is the owner of AGENT-1 which is PATIENT-2 long . AGENT-1 was built by PATIENT-3 and operated by BRIDGE-1 .</template>'):
                '<template>PATIENT-4 is the owner of AGENT-1 which is PATIENT-2 long . AGENT-1 was built by PATIENT-3 .</template>',
        }
        text = line.strip()
        key = (fname_end, line_ix, text)
        if key in filter_dic:
            new_text = filter_dic[key]
            if not new_text: return False

            line = line.replace(text, new_text)

        return line


ALPHA = chr(2)  # Start of text
OMEGA = chr(3)  # End of text
SPLITABLES = {ALPHA, OMEGA, " ", ".", ",", ":", "-", "'", "(", ")", "?", "!",
              "&", ";", '"'}


class DataReader:

    def __init__(self, data: List[dict],
                 misspelling: Dict[str, str] = None,
                 rephrase: Tuple[Callable, Callable] = (None, None)):
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

            self.data = [d.set_text(re.sub(source, target, d.text)) for d in
                         self.data]

        return self


class NLP:
    def __init__(self):

        self.nlp = spacy.load('en', disable=['ner', 'parser', 'tagger'])
        self.nlp.add_pipe(self.nlp.create_pipe('sentencizer'))

    def sent_tokenize(self, text):
        doc = self.nlp(text)
        sentences = [sent.string.strip() for sent in doc.sents]
        return sentences

    def word_tokenize(self, text, lower=False):  # create a tokenizer function
        if text is None: return text
        text = ' '.join(text.split())
        if lower: text = text.lower()
        toks = [tok.text for tok in self.nlp.tokenizer(text)]
        return ' '.join(toks)


def show_var(expression,
             joiner='\n', print=print):
    '''
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
    '''

    var_output = []

    for var_str in expression:
        frame = sys._getframe(1)
        value = eval(var_str, frame.f_globals, frame.f_locals)

        if ' object at ' in repr(value):
            value = vars(value)
            value = json.dumps(value, indent=2)
            var_output += ['{}: {}'.format(var_str, value)]
        else:
            var_output += ['{}: {}'.format(var_str, repr(value))]

    if joiner != '\n':
        output = "[Info] {}".format(joiner.join(var_output))
    else:
        output = joiner.join(var_output)
    print(output)
    return output


def fwrite(new_doc, path, mode='w', no_overwrite=False):
    if not path:
        print("[Info] Path does not exist in fwrite():", str(path))
        return
    if no_overwrite and os.path.isfile(path):
        print("[Error] pls choose whether to continue, as file already exists:",
              path)
        import pdb
        pdb.set_trace()
        return
    with open(path, mode) as f:
        f.write(new_doc)


def shell(cmd, working_directory='.', stdout=False, stderr=False):
    import subprocess
    from subprocess import PIPE, Popen

    subp = Popen(cmd, shell=True, stdout=PIPE,
                 stderr=subprocess.STDOUT, cwd=working_directory)
    subp_stdout, subp_stderr = subp.communicate()

    if stdout and subp_stdout:
        print("[stdout]", subp_stdout, "[end]")
    if stderr and subp_stderr:
        print("[stderr]", subp_stderr, "[end]")

    return subp_stdout, subp_stderr
