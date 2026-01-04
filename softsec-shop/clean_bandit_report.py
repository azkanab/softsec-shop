import re
from collections import Counter

INPUT_FILE = "bandit-report.txt"
OUTPUT_FILE = "bandit-report-cleaned.txt"
SEPARATOR = "-" * 50


def main():
    with open(INPUT_FILE, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    header, rest = text.split("Test results:", 1)
    issues_part, tail = rest.split("Code scanned:", 1)

    # Split issues by separator
    raw_blocks = issues_part.split(SEPARATOR)
    kept_blocks = []

    severity_counter = Counter()
    confidence_counter = Counter()

    for block in raw_blocks:
        if ">> Issue:" not in block:
            continue

        # Skip issues from bandit-env
        if re.search(r"Location:\s*\./bandit-env/", block):
            continue

        kept_blocks.append(block.strip())

        # Extract severity & confidence
        sev = re.search(r"Severity:\s*(\w+)", block)
        conf = re.search(r"Confidence:\s*(\w+)", block)
        if sev:
            severity_counter[sev.group(1)] += 1
        if conf:
            confidence_counter[conf.group(1)] += 1

    # Rebuild Test results section
    new_issues_section = "Test results:\n"
    for i, block in enumerate(kept_blocks):
        new_issues_section += block + "\n"
        if i != len(kept_blocks) - 1:
            new_issues_section += SEPARATOR + "\n"
    new_issues_section += "\n" + SEPARATOR + "\n"

    # Update metrics in tail
    def replace_metric(section, name, counts):
        for key in ["Undefined", "Low", "Medium", "High"]:
                section = re.sub(
                rf"({key}:\s*)\d+",
                rf"\g<1>{counts.get(key, 0)}",
                section,
                )
        return section

    tail = replace_metric(tail, "severity", severity_counter)
    tail = replace_metric(tail, "confidence", confidence_counter)

    cleaned = header + new_issues_section + "Code scanned:" + tail

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(cleaned)

    print(f"✅ Cleaned report written to {OUTPUT_FILE}")
    print(f"Removed {len(raw_blocks) - len(kept_blocks)} issues from ./bandit-env")


if __name__ == "__main__":
    main()
