import marimo

print(marimo.__version__)

def test_type_hints(a: int) -> str:
    return str(a)

def main():
    print("Hello from The Gaffer!")

    # x = test_type_hints("1")
    y = test_type_hints(1)
    # print(x)
    print(y)


if __name__ == "__main__":
    main()

# TODO:
# 1. configure my type check rules I want to use
# 2. configure precommit hook to run ty and ruff
# 3. add tests
# 4. add github CI to run the tests and lint / type checks
