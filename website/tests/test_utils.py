import pytest

from website.utils import (
    StableSet,
    columnify,
    count,
    flatlist,
    flatten,
    flow,
    group_and_count,
    group_by,
    immutablemap,
    invert,
    iremoveprefix,
    iremovesuffix,
    minmax,
    pull_if,
    remove_if,
    removeprefix,
    removesuffix,
    unique,
)


class TestUnique:
    def test_unique_preserves_order(self):
        assert "generator" in str(unique([]))
        assert list(unique([4, 2, 1, 4, 2, 3])) == [4, 2, 1, 3]
        assert list(unique([3, 2, 4, 1, 2, 4])) == [3, 2, 4, 1]
        assert list(unique([])) == []

    def test_unique_with_predicate(self):
        assert list(unique([4, 2, 1, 4, 2, 3], lambda x: x % 2)) == [4, 1]


class TestFlatten:
    def test_flattens_lists(self):
        assert flatten([[1, 2], [3, 4]]) == [1, 2, 3, 4]

    def test_flattens_generators(self):
        g1 = (i for i in [1, 2])
        g2 = (i for i in [3, 4])
        assert flatten(g for g in [g1, g2]) == [1, 2, 3, 4]


class TestFlow:
    def test_flows(self):
        f = flow([lambda x: x + 1, lambda x: x * 10])
        y = f(1)
        assert y == 20


class TestGroupBy:
    def test_group_by(self):
        f = group_by([1, 2, 3, 4, 5, 6, 7], lambda x: x % 2 == 0)
        assert f == {True: [2, 4, 6], False: [1, 3, 5, 7]}


class TestGroupAndCount:
    def test_group_and_count(self):
        f = group_and_count([1, 2, 3, 4, 5, 6, 7], lambda x: x % 2 == 0)
        assert f == {True: 3, False: 4}


class TestColumnify:
    def test_columnify(self):
        assert columnify("(AB)") == "a_b"
        assert columnify(" ABCD ") == "a_b_c_d"
        assert columnify("A (b1) C2 3 4d") == "a_b_1_c_2_3_4d"
        assert columnify("A (b) Cdd") == "a_b_cdd"
        assert columnify("A_(Ab) Cdd_)") == "a_ab_cdd"
        assert columnify("BaseCase1st") == "base_case_1st"
        assert columnify("OfferingID") == "offering_id"
        assert columnify("GSI ID") == "g_s_i_id"


class TestStableSet:
    def test_stable_ordering_and_sorting_behavior(self):
        ss = StableSet([3, 1, 2, 1])
        assert ss.to_list() == [3, 1, 2]
        ss.add(0)
        ss.add(4)
        ss.add(0)
        assert ss.to_list() == [3, 1, 2, 0, 4]
        ss.remove(2)
        ss.remove(2)
        ss.remove(4)
        assert ss.to_list() == [3, 1, 0]
        assert ss.to_list(sort=True) == [0, 1, 3]
        ss.union([1, 0, 5])
        assert ss.to_list() == [3, 1, 0, 5]
        ss.difference([0, 1, 2])
        assert ss.to_list() == [3, 5]


class TestFiltering:
    def test_remove_if_removes_values_matching_predicate(self):
        values = [1, 2, 3, 4, 5, 4]
        assert list(remove_if(values, lambda x: x % 2)) == [2, 4, 4]
        assert list(remove_if(values, invert(lambda x: x % 2))) == [1, 3, 5]
        assert len(values) == 6

    def test_pull_mutates_list(self):
        values = [1, 2, 3, 4, 5, 4]
        pull_if(values, lambda x: x % 2)
        assert values == [2, 4, 4]
        pull_if(values, invert(lambda x: x % 2))
        assert values == []


class TestFlatlist:
    def test_works(self):
        e = flatlist([], 1, [2, 3, 4], *[[5, 6], [7, 8]], 9, *[[0]])
        assert e == [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]


class TestImmutablemap:
    def test_immutability(self):
        d = {"x": 1, "y": 2, "z": 3}
        x = immutablemap(d)

        with pytest.raises(TypeError):
            x["foo"] = 1

        with pytest.raises(TypeError):
            x["x"] = 1

        with pytest.raises(TypeError):
            del x["x"]

        with pytest.raises(TypeError):
            x.clear()

        with pytest.raises(TypeError):
            x.update({"z": 2})

        with pytest.raises(TypeError):
            x.setdefault("v", 4)

        with pytest.raises(TypeError):
            x.popitem()

        assert x.items() == d.items()


class TestCount:
    def test_count(self):
        x = [1, 2, 3, 4, 5]
        assert count(x) == 5
        assert count(o for o in x) == 5
        assert count(x, lambda o: o >= 3) == 3


class TestMinMax:
    def test_minmax(self):
        x = [5, 2, 3, 7, 1]
        assert minmax([]) == (None, None)
        assert minmax([1]) == (1, 1)
        assert minmax(x) == (1, 7)
        assert minmax(x, key=lambda i: -1 * i) == (7, 1)

        noncomp_elements = [[i] for i in x]
        assert minmax(noncomp_elements, key=lambda i: i[0]) == ([1], [7])


class TestPrefixSuffix:
    def test_prefix_suffix(self):
        s = "ABC def"
        assert removeprefix(s, "ABC") == " def"
        assert removeprefix(s, "abc") == "ABC def"
        assert removeprefix(s, "X") == "ABC def"

        assert iremoveprefix(s, "ABC") == " def"
        assert iremoveprefix(s, "abc") == " def"
        assert iremoveprefix(s, "x") == "ABC def"

        assert removesuffix(s, "def") == "ABC "
        assert removesuffix(s, "DEF") == "ABC def"
        assert removesuffix(s, "X") == "ABC def"

        assert iremovesuffix(s, "def") == "ABC "
        assert iremovesuffix(s, "DEF") == "ABC "
        assert iremovesuffix(s, "X") == "ABC def"
