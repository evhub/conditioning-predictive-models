from undebt.pattern.util import (
    tokens_as_dict,
    tokens_as_list,
    attach,
)
from undebt.pyparsing import (
    Literal,
    SkipTo,
    OneOrMore,
    Optional,
    originalTextFor,
    nestedExpr,
    Word,
    Regex,
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

REST_OF_LINE = originalTextFor(NL | (ANY_CHAR | WHITE) + SkipTo(NL) + NL)

@tokens_as_list(assert_len=1)
def trim(tokens):
    return tokens[0][1:-1]

PARENS = attach(originalTextFor(Literal("(") + OneOrMore(~NL + ~Literal(")") + ANY_CHAR) + Literal(")")), trim)
BRACKETS = attach(originalTextFor(Literal("[") + OneOrMore(~NL + ~Literal("]") + ANY_CHAR) + Literal("]")), trim)
BRACES = attach(originalTextFor(Literal("{") + OneOrMore(~NL + ~Literal("}") + ANY_CHAR) + Literal("}")), trim)


# setup:
patterns_list = []


# header:
header_grammar = (
    NL + Literal("#") + NUM("num") + Literal(".") + REST_OF_LINE("name")
)

@tokens_as_dict(assert_keys=("num", "name"))
def header_replace(tokens):
    return "\n\\section{" + tokens["name"].rstrip() + "}\n\\label{sec:" + tokens["num"] + "}\n\\cftchapterprecistoc{TODO: toc section description}\n"

patterns_list.append((header_grammar, header_replace))


# unicode:
U_MAP = (
    ("—", "---"),
    ("“", "``"),
    ("”", "''"),
    ("’", "'"),
)

unicode_grammar = Literal(U_MAP[0][0])
for md, _ in U_MAP[1:]:
    unicode_grammar |= Literal(md)

@tokens_as_list(assert_len=1)
def unicode_replace(tokens):
    return dict(U_MAP)[tokens[0]]

patterns_list.append((unicode_grammar, unicode_replace))


# ital:
begin_ital = Regex(r"\b_")
end_ital = Regex(r"_\b")

ital_grammar = begin_ital + originalTextFor(OneOrMore(~end_ital + ~NL + ANY_CHAR))("text") + end_ital

@tokens_as_dict(assert_keys=("text",))
def ital_replace(tokens):
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


# enumerate:
enumerate_grammar = NL.suppress() + (
    (NUM + Literal(".")).suppress() + REST_OF_LINE
) + OneOrMore(
    (NUM + Literal(".")).suppress() + REST_OF_LINE
)

@tokens_as_list()
def enumerate_replace(tokens):
    return (
        "\n\\begin{enumerate}\n"
        + "".join("\item " + t.rstrip() + "\n" for t in tokens)
        + "\end{enumerate}\n"
    )

patterns_list.append((enumerate_grammar, enumerate_replace))


# itemize:
itemize_grammar = NL.suppress() + (
    Literal("-").suppress() + REST_OF_LINE
) + OneOrMore(
    Literal("-").suppress() + REST_OF_LINE
)

@tokens_as_list()
def itemize_replace(tokens):
    return (
        "\n\\begin{itemize}\n"
        + "".join("\item " + t.rstrip() + "\n" for t in tokens)
        + "\end{itemize}\n"
    )

patterns_list.append((itemize_grammar, itemize_replace))


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
    NL + Literal("[^") + NUM("num") + Literal("]:") + REST_OF_LINE("text")
)

@tokens_as_dict(assert_keys=("num", "text"))
def footnote_recorder_replace(tokens):
    footnote_dict[tokens["num"]] = tokens["text"]
    return ""

patterns_list.append((footnote_recorder_grammar, footnote_recorder_replace))


# footnote replacer:
footnote_dict = {}

footnote_replacer_grammar = Literal("[^") + NUM("num") + Literal("]")

@tokens_as_dict(assert_keys=("num",))
def footnote_replacer_replace(tokens):
    return "\\footnote{" + footnote_dict[tokens["num"]].rstrip() + "}"

patterns_list.append((footnote_replacer_grammar, footnote_replacer_replace))


# post:
post_grammar = (Literal("This") | Literal("this"))("this") + Literal("post")

@tokens_as_dict(assert_keys=("this",))
def post_replace(tokens):
    return tokens["this"] + " (TODO: post -> paper)"

patterns_list.append((post_grammar, post_replace))


# main:
def main(in_fname, out_fname):
    with open(in_fname, "tr", encoding="utf-8") as fp:
        text = fp.read()

    for i, (grammar, replace) in enumerate(patterns_list):
        print("running pattern {}...".format(replace.__name__[:-len("_replace")]))

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
