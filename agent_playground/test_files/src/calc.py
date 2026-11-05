"""Tiny calculator module used to test the coding agent."""


def add(a, b):
    """Return the sum of a and b."""
    return a + b


def subtract(a, b):
    """Return a minus b."""
    return a - b


def average(numbers):
    """Return the arithmetic mean of a non-empty list of numbers."""
    total = 0
    for n in numbers:
        total = add(total, n)
    return total / 2
