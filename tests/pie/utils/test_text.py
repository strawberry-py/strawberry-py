from typing import List

from pie import utils


def test_text_sanitise():
    assert "a\\*b" == utils.text.sanitise("a*b")
    assert "a\\_b" == utils.text.sanitise("a_b")


def test_text_split():
    assert ["abc", "def"] == utils.text.split("abcdef", limit=3)
    assert ["abcd", "efgh"] == utils.text.split("abcdefgh", limit=4)


def test_text_smart_split():
    assert ["abc", "def"] == utils.text.smart_split("abcdef", limit=3)
    assert ["abcd", "efgh"] == utils.text.smart_split("abcdefgh", limit=4)
    assert [
        "Lorem ipsum dolor sit amet,",
        "consectetuer adipiscing elit.",
    ] == utils.text.smart_split(
        "Lorem ipsum dolor sit amet, consectetuer adipiscing elit.", limit=47
    )
    assert [
        "Lorem ipsum dolor sit amet, consectetuer",
        "adipiscing elit.",
    ] == utils.text.smart_split(
        "Lorem ipsum dolor sit amet, consectetuer adipiscing elit.", limit=49
    )
    assert [
        "Lorem ipsum dolor sit amet, consectetuer",
        "adipiscing elit.",
    ] == utils.text.smart_split(
        "Lorem ipsum dolor sit amet, consectetuer adipiscing elit.", limit=51
    )
    assert [
        "Lorem ipsum dolor sit amet, consectetuer",
        "***Continuation***\nadipiscing elit.",
    ] == utils.text.smart_split(
        "Lorem ipsum dolor sit amet, consectetuer adipiscing elit.",
        limit=51,
        mark_continuation="***Continuation***\n",
    )
    assert [
        "Lorem ipsum dolor sit amet, consectetuer",
        "adipiscing elit.",
    ] == utils.text.smart_split(
        "Lorem ipsum dolor sit amet, consectetuer adipiscing elit.",
        limit=51,
        mark_continuation="",
    )
    assert [
        "Lorem ipsum dolor sit amet, consectetuer",
        "__shrug__adipiscing elit.",
    ] == utils.text.smart_split(
        "Lorem ipsum dolor sit amet, consectetuer adipiscing elit.",
        limit=51,
        mark_continuation="__shrug__",
    )
    assert [
        "Lorem ipsum dolor sit amet, consectetuer",
        "adipiscing elit.",
    ] == utils.text.smart_split(
        "Lorem ipsum dolor sit amet, consectetuer adipiscing elit.",
        limit=51,
        mark_continuation=None,
    )
    assert [
        "Lorem ipsum dolor sit amet,",
        "***Continuation***\n***consectetuer adipiscing***",
        "***Continuation***\nelit.",
    ] == utils.text.smart_split(
        "Lorem ipsum dolor sit amet, ***consectetuer adipiscing*** elit.",
        limit=51,
        min_length=25,
        mark_continuation="***Continuation***\n",
    )
    assert [
        "# Lorem ipsum dolor sit amet, consectetuer",
        "***Continuation***\n# adipiscing elit.",
    ] == utils.text.smart_split(
        "# Lorem ipsum dolor sit amet, consectetuer adipiscing elit.",
        limit=51,
        mark_continuation="***Continuation***\n",
    )
    assert [
        "# Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Fusce aliquam vestibulum ipsum. Phasellus faucibus "
        + "molestie nisl. Etiam sapien elit, consequat eget, tristique non, venenatis quis, ante. Duis aute irure dolor "
        + "in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Pellentesque sapien. Etiam "
        + "egestas wisi a erat. Fusce suscipit libero eget elit. Nullam sit amet magna in magna gravida vehicula. Nulla "
        + "turpis magna, cursus sit amet, suscipit a, interdum id, felis. Temporibus autem quibusdam et aut officiis "
        + "debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non "
        + "recusandae. Aliquam in lorem sit amet leo accumsan lacinia. Duis sapien nunc, commodo et, interdum suscipit, "
        + "sollicitudin et, dolorClass aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos "
        + "hymenaeos. Nulla non arcu lacinia neque faucibus fringilla. Nemo enim ipsam voluptatem quia voluptas sit "
        + "aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi "
        + "nesciunt. Maecenas libero. Nullam sit amet magna in magna gravida vehicula. Integer tempor. In laoreet, "
        + "magna id viverra tincidunt, sem odio bibendum justo, vel imperdiet sapien wisi sed libero. Nunc tincidunt "
        + "ante vitae massa. Nullam dapibus fermentum ipsum. Vestibulum fermentum tortor id mi. In rutrum. Etiam sapien "
        + "elit, consequat eget, tristique non, venenatis quis, ante. Duis viverra diam non justo. Fusce aliquam "
        + "vestibulum ipsum. Aliquam ante.Etiam bibendum elit eget erat. Nullam at arcu a est sollicitudin euismod. "
        + "Fusce wisi. Nullam sit amet magna in magna gravida vehicula. Quis autem vel eum iure reprehenderit qui in ea "
        + "voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla "
        + "pariatur? Aliquam erat volutpat. Nulla accumsan, elit sit amet varius semper, nulla mauris mollis quam, "
        + "tempor suscipit diam nulla vel leo. Pellentesque pretium lectus id",
        "***Continuation***\n# turpis. Nemo enim ipsam volup",
    ] == utils.text.smart_split(
        "# Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Fusce aliquam vestibulum ipsum. Phasellus faucibus "
        + "molestie nisl. Etiam sapien elit, consequat eget, tristique non, venenatis quis, ante. Duis aute irure dolor "
        + "in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Pellentesque sapien. Etiam "
        + "egestas wisi a erat. Fusce suscipit libero eget elit. Nullam sit amet magna in magna gravida vehicula. Nulla "
        + "turpis magna, cursus sit amet, suscipit a, interdum id, felis. Temporibus autem quibusdam et aut officiis "
        + "debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non "
        + "recusandae. Aliquam in lorem sit amet leo accumsan lacinia. Duis sapien nunc, commodo et, interdum suscipit, "
        + "sollicitudin et, dolorClass aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos "
        + "hymenaeos. Nulla non arcu lacinia neque faucibus fringilla. Nemo enim ipsam voluptatem quia voluptas sit "
        + "aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi "
        + "nesciunt. Maecenas libero. Nullam sit amet magna in magna gravida vehicula. Integer tempor. In laoreet, "
        + "magna id viverra tincidunt, sem odio bibendum justo, vel imperdiet sapien wisi sed libero. Nunc tincidunt "
        + "ante vitae massa. Nullam dapibus fermentum ipsum. Vestibulum fermentum tortor id mi. In rutrum. Etiam sapien "
        + "elit, consequat eget, tristique non, venenatis quis, ante. Duis viverra diam non justo. Fusce aliquam "
        + "vestibulum ipsum. Aliquam ante.Etiam bibendum elit eget erat. Nullam at arcu a est sollicitudin euismod. "
        + "Fusce wisi. Nullam sit amet magna in magna gravida vehicula. Quis autem vel eum iure reprehenderit qui in ea "
        + "voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla "
        + "pariatur? Aliquam erat volutpat. Nulla accumsan, elit sit amet varius semper, nulla mauris mollis quam, "
        + "tempor suscipit diam nulla vel leo. Pellentesque pretium lectus id turpis. Nemo enim ipsam volup",
        mark_continuation="***Continuation***\n",
    )
    assert [
        "Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Fusce aliquam vestibulum ipsum. Phasellus faucibus "
        + "molestie nisl. Etiam sapien elit, consequat eget, tristique non, venenatis quis, ante. Duis aute irure dolor "
        + "in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Pellentesque sapien. Etiam "
        + "egestas wisi a erat. Fusce suscipit libero eget elit. Nullam sit amet magna in magna gravida vehicula. Nulla "
        + "turpis magna, cursus sit amet, suscipit a, interdum id, felis. Temporibus autem quibusdam et aut officiis "
        + "debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non "
        + "recusandae. Aliquam in lorem sit amet leo accumsan lacinia. Duis sapien nunc, commodo et, interdum suscipit, "
        + "sollicitudin et, dolorClass aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos "
        + "hymenaeos. Nulla non arcu lacinia neque faucibus fringilla. Nemo enim ipsam voluptatem quia voluptas sit "
        + "aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi "
        + "nesciunt. Maecenas libero. Nullam sit amet magna in magna gravida vehicula. Integer tempor. In laoreet, "
        + "magna id viverra tincidunt, sem odio bibendum justo, vel imperdiet sapien wisi sed libero. Nunc tincidunt "
        + "ante vitae massa. Nullam dapibus fermentum ipsum. Vestibulum fermentum tortor id mi. In rutrum. Etiam sapien "
        + "elit, consequat eget, tristique non, venenatis quis, ante. Duis viverra diam non justo. Fusce aliquam "
        + "vestibulum ipsum. Aliquam ante.Etiam bibendum elit eget erat. Nullam at arcu a est sollicitudin euismod. "
        + "Fusce wisi. Nullam sit amet magna in magna gravida vehicula. Quis autem vel eum iure reprehenderit qui in ea "
        + "voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla "
        + "pariatur? Aliquam erat volutpat. Nulla accumsan, elit sit amet varius semper, nulla mauris mollis quam, "
        + "tempor suscipit diam nulla vel leo.",
        "***Continuation***\n__***Pellentesque pretium lectus id turpis. Nemo enim***__ ipsam volup",
    ] == utils.text.smart_split(
        "Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Fusce aliquam vestibulum ipsum. Phasellus faucibus "
        + "molestie nisl. Etiam sapien elit, consequat eget, tristique non, venenatis quis, ante. Duis aute irure dolor "
        + "in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Pellentesque sapien. Etiam "
        + "egestas wisi a erat. Fusce suscipit libero eget elit. Nullam sit amet magna in magna gravida vehicula. Nulla "
        + "turpis magna, cursus sit amet, suscipit a, interdum id, felis. Temporibus autem quibusdam et aut officiis "
        + "debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non "
        + "recusandae. Aliquam in lorem sit amet leo accumsan lacinia. Duis sapien nunc, commodo et, interdum suscipit, "
        + "sollicitudin et, dolorClass aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos "
        + "hymenaeos. Nulla non arcu lacinia neque faucibus fringilla. Nemo enim ipsam voluptatem quia voluptas sit "
        + "aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi "
        + "nesciunt. Maecenas libero. Nullam sit amet magna in magna gravida vehicula. Integer tempor. In laoreet, "
        + "magna id viverra tincidunt, sem odio bibendum justo, vel imperdiet sapien wisi sed libero. Nunc tincidunt "
        + "ante vitae massa. Nullam dapibus fermentum ipsum. Vestibulum fermentum tortor id mi. In rutrum. Etiam sapien "
        + "elit, consequat eget, tristique non, venenatis quis, ante. Duis viverra diam non justo. Fusce aliquam "
        + "vestibulum ipsum. Aliquam ante.Etiam bibendum elit eget erat. Nullam at arcu a est sollicitudin euismod. "
        + "Fusce wisi. Nullam sit amet magna in magna gravida vehicula. Quis autem vel eum iure reprehenderit qui in ea "
        + "voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla "
        + "pariatur? Aliquam erat volutpat. Nulla accumsan, elit sit amet varius semper, nulla mauris mollis quam, "
        + "tempor suscipit diam nulla vel leo. __***Pellentesque pretium lectus id turpis. Nemo enim***__ ipsam volup",
        mark_continuation="***Continuation***\n",
    )


def test_text_split_lines():
    assert ["ab\ncd", "ef\ng"] == utils.text.split_lines(
        ["ab", "cd", "ef", "g"], limit=5
    )
    assert ["abc\ndef", "g"] == utils.text.split_lines(["abc", "def", "g"], limit=7)


def test_text_create_table():
    class Item:
        a: int
        b: str

        def __init__(self, a, b):
            self.a = a
            self.b = b

    iterable = [Item(1, "a"), Item(123456789, "b"), Item(3, "abcdefghijk")]
    header = {
        "a": "Integer",
        "b": "String",
    }
    expected = (
        "Integer    String\n"
        "1          a\n"
        "123456789  b\n"
        "3          abcdefghijk\n"
    )
    table: str = utils.text.create_table(iterable, header, rich=False)
    assert [expected] == table


def test_text_create_table_noattr():
    class Item:
        a: int
        b: str

        def __init__(self, a, b):
            self.a = a
            if a != 2:
                self.b = b

    iterable = [Item(1, "a"), Item(2, "b"), Item(3, "c")]
    header = {
        "a": "int",
        "b": "str",
    }
    expected = "int  str\n" "1    a\n" "2\n" "3    c\n"
    table: str = utils.text.create_table(iterable, header, rich=False)
    assert [expected] == table


def test_text_create_table_wrapped():
    class Item:
        a: int
        b: str

        def __init__(self, a, b):
            self.a = a
            self.b = b

    iterable = [Item(1111, "aaaa"), Item(2222, "bbbb")]
    header = {
        "a": "Integer",
        "b": "String",
    }
    page_1 = "Integer  String\n" "1111     aaaa\n"
    page_2 = "2222     bbbb\n"
    table: List[str] = utils.text.create_table(iterable, header, limit=32, rich=False)
    assert [page_1, page_2] == table


def test_text_create_table_colors():
    class Item:
        a: int
        b: str

        def __init__(self, a, b):
            self.a = a
            self.b = b

    iterable = [Item(1, "a"), Item(123456789, "b"), Item(3, "abcdefghijk")]
    header = {
        "a": "Integer",
        "b": "String",
    }
    expected = (
        "ansi\n"
        "\x1b[1;34mInteger    String\x1b[0m\n"
        "1          a\n"
        "\x1b[36m123456789  b\x1b[0m\n"
        "3          abcdefghijk\n"
    )

    table: str = utils.text.create_table(iterable, header)
    assert [expected] == table
