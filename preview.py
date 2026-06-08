import sys

from simple_chunk import build_chunks


def print_first_five_chunks(chunks):
    professors = {}
    for chunk in chunks:
        professors.setdefault(chunk["professor"], []).append(chunk)

    for professor, professor_chunks in professors.items():
        print("=" * 80)
        print(professor)
        print("=" * 80)

        for chunk in professor_chunks[:5]:
            print(f"Chunk ID: {chunk['chunk_id']}")
            print(chunk["text"])
            print("-" * 80)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    chunks = build_chunks()
    print(f"Created {len(chunks)} chunks total.")
    print_first_five_chunks(chunks)
    print(f"Total chunks: {len(chunks)}")


if __name__ == "__main__":
    main()
