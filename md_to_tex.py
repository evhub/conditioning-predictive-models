from functools import partial

from undebt.pattern.util import (
    tokens_as_dict,
    tokens_as_list,
    attach,
)
from undebt.pyparsing import (
    Literal,
    SkipTo,
    OneOrMore,
    ZeroOrMore,
    Optional,
    originalTextFor,
    Word,
    Regex,
    Group,
    oneOf,
    nestedExpr,
)
from undebt.pattern.common import (
    NL,
    ANY_CHAR,
    WHITE,
)
from undebt.cmd.logic import (
    create_find_and_replace,
    parse_grammar,
    _transform_results,
)


# util:
NUM = originalTextFor(Word("0123456789"))

def SkipToAndThen(item):
    return SkipTo(item) + item

def everything_up_to(item):
    return originalTextFor(item | (ANY_CHAR | WHITE) + SkipToAndThen(item))

REST_OF_LINE = everything_up_to(NL)
UNTIL_NL_NL = everything_up_to(NL + NL)

@tokens_as_list(assert_len=1)
def trim(tokens):
    return tokens[0][1:-1]

PARENS = attach(originalTextFor(Literal("(") + OneOrMore(~NL + ~oneOf("( )") + ANY_CHAR) + Literal(")")), trim)
BRACKETS = attach(originalTextFor(Literal("[") + OneOrMore(~NL + ~oneOf("[ ]") + ANY_CHAR) + Literal("]")), trim)
BRACES = attach(originalTextFor(Literal("{") + OneOrMore(~NL + ~oneOf("{ }") + ANY_CHAR) + Literal("}")), trim)

def indent_by(indent, text):
    out_lines = []
    for line in text.splitlines(True):
        if line:
            line = indent + line
        out_lines.append(line)
    return "".join(out_lines)

def TwoOrMore(item):
    return item + OneOrMore(item)

def condense(item):
    return attach(item, "".join)


# setup:
patterns_list = []


# section:
section_grammar = (
    NL + Literal("#") + NUM("num") + Literal(".") + REST_OF_LINE("name")
)

@tokens_as_dict(assert_keys=("num", "name"))
def section_replace(tokens):
    return "\n\\section{" + tokens["name"].rstrip() + "}\n\\label{sec:" + tokens["num"] + "}\n\\cftchapterprecistoc{TODO: toc section description}\n"

patterns_list.append((section_grammar, section_replace))


# numbered subsection:
@tokens_as_dict()
def subsection_replace(tokens):
    out = "\n\\subsection{" + tokens["name"].rstrip() + "}"
    if "num" in tokens:
        out += "\n\\label{sec:" + "".join(tokens["num"]) + "}"
    out += "\n\\cftchapterprecistoc{TODO: toc section description}\n"
    return out

subsection_grammar = (
    NL + Literal("##") + ~Literal("#") + Optional(ANY_CHAR + ANY_CHAR + Literal(".").suppress())("num") + REST_OF_LINE("name")
)

patterns_list.append((subsection_grammar, subsection_replace))


# special chars:
patterns_list += [
    ("—", "---"),
    ("“", "``"),
    ("”", "''"),
    ("’", "'"),
    ("$", "$$"),
]


# ital:
begin_ital = Regex(r"\b_")
end_ital = Regex(r"_\b")

ital_grammar = begin_ital + originalTextFor(OneOrMore(~end_ital + ~NL + ANY_CHAR))("text") + end_ital

@tokens_as_dict(assert_keys=("text",))
def ital_replace(tokens):
    if tokens["text"].startswith("This is the ") and "Each post in the sequence corresponds to a different section of the paper." in tokens["text"]:
        return ""
    return "\\textit{" + tokens["text"] + "}"

patterns_list.append((ital_grammar, ital_replace))


# bf:
begin_bf = Literal("**")
end_bf = Literal("**")

bf_grammar = begin_bf + originalTextFor(OneOrMore(~end_bf + ~NL + ANY_CHAR))("text") + end_bf

@tokens_as_dict(assert_keys=("text",))
def bf_replace(tokens):
    return "\\textbf{" + tokens["text"] + "}"

patterns_list.append((bf_grammar, bf_replace))


# mark indents:
RAW_INDENT = " " * 4
RAW_INDENT_MARKER = "<INDENT>"

patterns_list.append((RAW_INDENT, RAW_INDENT_MARKER))


# enumerate/itemize:
MAX_INDENTS = 4

def enumerate_or_itemize_replace(name, tokens):
    out_lines = []
    initial_indent = None
    for item_toks in tokens:
        if len(item_toks) == 1:
            indent, item = "", item_toks[0]
        else:
            indent, item = item_toks
        out_lines.append(indent + "\\item " + item.rstrip())
        initial_indent = initial_indent or indent
    out_lines = ["", initial_indent + "\\begin{" + name + "}"] + out_lines
    out_lines += [initial_indent + "\\end{" + name + "}", ""]
    return "\n".join(out_lines)

@tokens_as_list()
def enumerate_replace(tokens):
    return enumerate_or_itemize_replace("enumerate", tokens)

@tokens_as_list()
def itemize_replace(tokens):
    return enumerate_or_itemize_replace("itemize", tokens)

INDENT_MARKER = Literal(RAW_INDENT_MARKER)

for num_indents in reversed(range(MAX_INDENTS + 1)):
    INDENT = Literal(RAW_INDENT_MARKER * num_indents)

    apply_indents = partial(indent_by, RAW_INDENT * num_indents)

    rest_of_line_and_maybe_inner_list = condense(
        REST_OF_LINE
        + Optional(originalTextFor(ZeroOrMore(INDENT_MARKER) + nestedExpr("\\begin{enumerate}", "\\end{enumerate}") + NL))
        + Optional(originalTextFor(ZeroOrMore(INDENT_MARKER) + nestedExpr("\\begin{itemize}", "\\end{itemize}") + NL))
    )

    # enumerate:
    enumerate_grammar = NL.suppress() + OneOrMore(Group(
        INDENT + (NUM + Literal(".")).suppress() + rest_of_line_and_maybe_inner_list
    ))

    patterns_list.append((enumerate_grammar, enumerate_replace))

    # itemize:
    itemize_grammar = NL.suppress() + OneOrMore(Group(
        INDENT + Literal("*").suppress() + rest_of_line_and_maybe_inner_list
    ))

    patterns_list.append((itemize_grammar, itemize_replace))


# unmark indents:
patterns_list.append((RAW_INDENT_MARKER, RAW_INDENT))


# figure:
figure_grammar = (
    NL + Literal("![]") + PARENS("link") + OneOrMore(NL)
    + Literal("\\textit") + BRACES("caption")
)

@tokens_as_dict(assert_keys=("link", "caption"))
def figure_replace(tokens):
    return r"""\begin{figure}[h!]
  \centering
  \includegraphics[width=(TODO: some float multiple of)\textwidth]{TODO: download %s}
  \caption{%s}
\end{figure}""" % (tokens["link"], tokens["caption"])

patterns_list.append((figure_grammar, figure_replace))


# link:
link_grammar = BRACKETS("text") + PARENS("link")

@tokens_as_dict(assert_keys=("text", "link"))
def link_replace(tokens):
    return tokens["text"] + "\cite{TODO: cite " + tokens["link"] + "}"

patterns_list.append((link_grammar, link_replace))


# footnote recorder:
footnote_dict = {}

footnote_recorder_grammar = (
    NL + Literal("[^") + NUM("num") + Literal("]:") + NL + UNTIL_NL_NL("text")
)

@tokens_as_dict(assert_keys=("num", "text"))
def footnote_recorder_replace(tokens):
    text_lines = []
    for line in tokens["text"].strip().splitlines():
        text_lines.append(line.strip())
    footnote_text = "\n".join(text_lines)
    assert footnote_text.strip(), f"got no text for footnote {tokens['num']!r}"
    assert tokens["num"] not in footnote_dict, f"duplicate footnote declaration: {tokens['num']!r}"
    footnote_dict[tokens["num"]] = footnote_text
    return "\n"

patterns_list.append((footnote_recorder_grammar, footnote_recorder_replace))


# footnote replacer:
seen_footnotes = set()

footnote_replacer_grammar = Literal("[^") + NUM("num") + Literal("]")

@tokens_as_dict(assert_keys=("num",))
def footnote_replacer_replace(tokens):
    assert tokens["num"] not in seen_footnotes, f"duplicate footnote reference: {tokens['num']!r}"
    seen_footnotes.add(tokens["num"])
    try:
        return "\\footnote{" + footnote_dict[tokens["num"]] + "}"
    except:
        print(f"known footnotes: {footnote_dict.keys()}")
        raise

patterns_list.append((footnote_replacer_grammar, footnote_replacer_replace))


# # post:
# post_grammar = (Literal("This") | Literal("this"))("this") + Literal("post")

# @tokens_as_dict(assert_keys=("this",))
# def post_replace(tokens):
#     return tokens["this"] + " (TODO: post -> paper)"

# patterns_list.append((post_grammar, post_replace))


# main:
def main(in_fname, out_fname):
    with open(in_fname, "tr", encoding="utf-8") as fp:
        text = fp.read()

    for i, (grammar, replace) in enumerate(patterns_list):
        if isinstance(grammar, str):
            print(f"replacing {grammar!r} with {replace!r}...")
            text = text.replace(grammar, replace)

        else:
            print("running pattern {}...".format(replace.__name__.removesuffix("_replace")))

            # keep running grammar until it stops producing results
            j = 0
            while True:
                print("\tpass {}...".format(j + 1))
                j += 1
                find_and_replace = create_find_and_replace(grammar, replace)
                results = parse_grammar(find_and_replace, text)
                if not results:
                    break
                else:
                    text = _transform_results(results, text)

    with open(out_fname, "tw", encoding="utf-8") as fp:
        fp.write(text)

if __name__ == "__main__":
    main("./posts.md", "./posts.tex")
    # from coconut import embed; embed()
