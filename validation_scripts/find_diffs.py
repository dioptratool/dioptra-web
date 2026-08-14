import argparse
import csv
import json
import math
import sys

# Tolerance for numeric comparisons: recomputed floats routinely differ in the
# last digits without being meaningfully different.
REL_TOL = 1e-6
ABS_TOL = 1e-4


def numbers_close(value1, value2):
    try:
        return math.isclose(float(value1), float(value2), rel_tol=REL_TOL, abs_tol=ABS_TOL)
    except (TypeError, ValueError):
        return None


def json_equal(value1, value2):
    if isinstance(value1, dict) and isinstance(value2, dict):
        return value1.keys() == value2.keys() and all(json_equal(value1[k], value2[k]) for k in value1)
    if isinstance(value1, list) and isinstance(value2, list):
        return len(value1) == len(value2) and all(json_equal(a, b) for a, b in zip(value1, value2))
    if isinstance(value1, bool) or isinstance(value2, bool):
        return value1 == value2
    close = numbers_close(value1, value2)
    if close is not None:
        return close
    return value1 == value2


def values_equal(value1, value2):
    """
    Equal exactly, numerically within tolerance, or as JSON documents compared
    recursively with numeric tolerance (for the output_costs_all /
    subcomponent_averages columns).
    """
    if value1 == value2:
        return True
    if value1 is None or value2 is None:
        return False
    close = numbers_close(value1, value2)
    if close is not None:
        return close
    try:
        parsed1, parsed2 = json.loads(value1), json.loads(value2)
    except (TypeError, ValueError):
        return False
    return json_equal(parsed1, parsed2)


def main():
    parser = argparse.ArgumentParser(description="Compare two CSV files containing analysis statuses.")
    parser.add_argument("file1", help="Path to the first (old) CSV file")
    parser.add_argument("file2", help="Path to the second (new) CSV file")
    parser.add_argument(
        "--allow-transition",
        action="append",
        default=[],
        metavar="OLD:NEW",
        help="Status transition to ignore, e.g. --allow-transition set-contribution:categorize "
        "for a release that removed a step. Repeatable.",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Always exit 0, even when differences are found.",
    )
    args = parser.parse_args()

    allowed_transitions = set()
    for transition in args.allow_transition:
        old, sep, new = transition.partition(":")
        if not sep:
            parser.error(f"--allow-transition must look like OLD:NEW, got {transition!r}")
        allowed_transitions.add((old, new))

    file1_data = {}
    file2_data = {}

    with open(args.file1, newline="") as csvfile1:
        reader1 = csv.DictReader(csvfile1)
        columns = list(reader1.fieldnames)
        for row in reader1:
            file1_data[row["id"]] = row

    with open(args.file2, newline="") as csvfile2:
        reader2 = csv.DictReader(csvfile2)
        for row in reader2:
            file2_data[row["id"]] = row

    all_ids = sorted(set(file1_data.keys()) | set(file2_data.keys()))

    differences = {}
    extra_rows = []

    for id_ in all_ids:
        if id_ not in file1_data or id_ not in file2_data:
            extra_rows.append((id_, args.file1 if id_ in file1_data else args.file2))
            continue

        row1 = file1_data[id_]
        row2 = file2_data[id_]
        diff_columns = []
        for col in columns:
            value1 = row1.get(col)
            value2 = row2.get(col)

            # A column missing from one file (old/new snapshot format skew)
            # cannot be meaningfully compared.
            if value1 is None or value2 is None:
                continue

            if col == "status" and (value1, value2) in allowed_transitions:
                continue

            if col == "output_cost":
                # Ignore differences if output_cost is missing in one of the files
                if not value1 or not value2:
                    continue

            if not values_equal(value1, value2):
                diff_columns.append(col)
        if diff_columns:
            differences[id_] = {
                "diff_columns": diff_columns,
                "row1": row1,
                "row2": row2,
            }

    if differences:
        print(f"{len(differences)} Differences:")

    for id_, diff_info in differences.items():
        diff_cols = ", ".join(diff_info["diff_columns"])
        print()

        print(f"| {diff_cols} change | " + " | ".join(columns) + " |")
        print("| -- |" + " -- |" * len(columns))

        row1_str = " | ".join([diff_info["row1"].get(col) or "" for col in columns])
        row2_str = " | ".join([diff_info["row2"].get(col) or "" for col in columns])
        print(f"| **Old** | {row1_str} |")
        print(f"| **New** | {row2_str} |")

    if extra_rows:
        for id_, containing_file in extra_rows:
            print(f"ID {id_} is only in {containing_file}.")

    if not differences and not extra_rows:
        print("No differences found in analysis statuses.")

    if (differences or extra_rows) and not args.no_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
