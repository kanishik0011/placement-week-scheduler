from app.generator import generate_dataset


def test_default_dataset_counts_and_determinism():
    one = generate_dataset(42)
    two = generate_dataset(42)
    assert len(one.students) == 800
    assert len(one.companies) == 35
    assert len(one.rooms) == 20
    assert len(one.interviews) > 0
    assert one.to_dict() == two.to_dict()


def test_shortlists_are_realistic_and_top_students_overlap_more():
    dataset = generate_dataset(42)
    shortlist_sizes = [c.shortlist_size for c in dataset.companies]
    assert max(shortlist_sizes) >= 300
    assert min(shortlist_sizes) <= 60
    counts = [len(s.shortlisted_company_ids) for s in dataset.students]
    top = sorted(dataset.students, key=lambda s: s.cgpa, reverse=True)[:80]
    bottom = sorted(dataset.students, key=lambda s: s.cgpa)[:80]
    assert sum(len(s.shortlisted_company_ids) for s in top) / len(top) > sum(len(s.shortlisted_company_ids) for s in bottom) / len(bottom)
    assert sum(1 for c in dataset.companies if c.shortlist_size >= 200) >= 5
    assert max(counts) >= 5
