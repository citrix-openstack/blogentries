import sys

lines = sys.stdin.readlines()

def converted(l1, l2):
    if l2 is None:
        return l1
    if l1.strip() and l2.strip() and not (l1.startswith('-') or l1.startswith(' ') or l1.startswith('#')):
        return l1[:-1] + " "
    return l1


for line1, line2 in zip(lines, lines[1:] + [None]):
    sys.stdout.write(converted(line1, line2))
