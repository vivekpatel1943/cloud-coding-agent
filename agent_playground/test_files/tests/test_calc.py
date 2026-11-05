from src.calc import add, average, subtract


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2


def test_average():
    assert average([1, 2, 3, 4]) == 2.5
