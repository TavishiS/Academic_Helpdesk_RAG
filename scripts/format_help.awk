# Formats `make help` for the terminal width (used by the Makefile).
#
# A line "  <command>  <description>" (command and description separated by 2+ spaces)
# is wrapped at word boundaries so that continuation lines start under the first word
# of the description, not under the command. Other long lines keep their indentation.
#
#   awk -v width=100 -f scripts/format_help.awk

function wrap(line,    col, s, rest, p, head, n, w, i, out, len) {
    col = match(line, /[^ ]/) - 1                 # default: hang under the line's own indentation
    rest = substr(line, col + 1)
    if (col > 0 && (p = index(rest, "  ")) > 0) {  # two columns: find where the description starts
        s = col + p
        while (substr(line, s + 1, 1) == " ") s++
        col = s
    }
    head = substr(line, 1, col)
    n = split(substr(line, col + 1), w, " ")
    out = head; len = col
    for (i = 1; i <= n; i++) {
        if (len > col && len + 1 + length(w[i]) > width) {   # word does not fit: start a new line
            print out
            out = sprintf("%" col "s", ""); len = col
        }
        if (len > col) { out = out " "; len++ }
        out = out w[i]; len += length(w[i])
    }
    print out
}

{
    if (length($0) <= width || $0 !~ /[^ ]/) print
    else wrap($0)
}
