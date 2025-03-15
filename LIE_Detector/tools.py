def has_intersection(list1, list2):
    return not set(list1).isdisjoint(list2)

def write_test_code_to_testdisplay(test_code):
    with open("example.py", "w", encoding="utf-8") as file:
        file.write(test_code)

