"""Inspect the generated population without preparing or writing any dataset."""
from .data.access import ContextStore


def main():
    store = ContextStore()
    for split in ('train', 'validation', 'test'):
        students = store.load(split)
        anchors = {student.lineage.source_anchor_student_id for student in students}
        print(f'{split}: {len(students)} synthetic students from {len(anchors)} source anchors')


if __name__ == '__main__':
    main()
