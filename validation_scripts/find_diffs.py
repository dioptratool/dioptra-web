import argparse
import csv


def main():
    parser = argparse.ArgumentParser(description="Compare two CSV files containing analysis statuses.")
    parser.add_argument("file1", help="Path to the first CSV file")
    parser.add_argument("file2", help="Path to the second CSV file")
    args = parser.parse_args()

    file1 = args.file1
    file2 = args.file2

    file1_data = {}
    file2_data = {}

    with open(file1, newline="") as csvfile1:
        reader1 = csv.DictReader(csvfile1)
        columns = list(reader1.fieldnames)
        for row in reader1:
            id_ = row["id"]
            file1_data[id_] = row

    with open(file2, newline="") as csvfile2:
        reader2 = csv.DictReader(csvfile2)
        # Assuming both files have the same structure and columns
        for row in reader2:
            id_ = row["id"]
            file2_data[id_] = row

    all_ids = sorted(set(file1_data.keys()) | set(file2_data.keys()))

    differences = {}
    extra_rows = []

    for id_ in all_ids:
        if id_ in file1_data and id_ in file2_data:
            row1 = file1_data[id_]
            row2 = file2_data[id_]
            diff_columns = []
            for col in columns:
                value1 = row1.get(col)
                value2 = row2.get(col)

                if col == "status":
                    pass

                    # These are examples of exceptions made in previous runs of this script.
                    #  You may need to add to these for a single run
                    # # fix-missing-data was removed in 1.15
                    # if value2 == "load-data" and value1 == "fix-missing-data":
                    #     continue

                    # # set-contribution was removed in 1.15
                    # if value2 == "categorize" and value1 == "set-contribution":
                    #     continue

                    # # categorize is done automatically in 1.15
                    # if value2 == "categorize" and value1 == "load-data":
                    #     continue

                if col == "output_cost":
                    # Ignore differences if output_cost is missing in one of the files
                    if not value1 or not value2:
                        continue
                    elif value1 != value2:
                        diff_columns.append(col)
                else:
                    if value1 != value2:
                        diff_columns.append(col)
            if diff_columns:
                differences[id_] = {
                    "diff_columns": diff_columns,
                    "row1": row1,
                    "row2": row2,
                }
        else:
            extra_rows.append(id_)

    if differences:
        print(f"{len(differences)} Differences:")

    for id_, diff_info in differences.items():
        diff_cols = ", ".join(diff_info["diff_columns"])
        print()

        print(f"| {diff_cols} change | ID | Step | Last Updated Date | Output Cost |")
        print("| -- | " + " -- |" * (len(columns)))

        row1_str = " | ".join([diff_info["row1"][col] for col in columns])
        row2_str = " | ".join([diff_info["row2"][col] for col in columns])
        print(f"| **Old** | {row1_str} |")
        print(f"| **New** | {row2_str} |")

    if extra_rows:
        for id_ in extra_rows:
            print(f"ID {id_} is only in one file.")

    if not differences:
        print("No differences found in analysis statuses.")


if __name__ == "__main__":
    main()
