def example_function(a: int) -> str:
    if a < 0:
        raise ValueError("a must be greater than 0")
    return str(a)
