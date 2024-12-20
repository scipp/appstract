# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
from typing import Union

import pytest

from appstract.constructors import (
    InsufficientAnnotationError,
    Provider,
    SingletonProvider,
    SingletonProviderCalledWithDifferentArgs,
)
from appstract.constructors._test_helpers import (
    Adult,
    GoodTelling,
    Joke,
    Parent,
    lime_joke,
    make_a_joke,
    make_another_joke,
    orange_joke,
)
from appstract.constructors.providers import UnknownProvider, UnknownProviderCalled


def test_provider_function_call():
    joke_provider = Provider(make_a_joke)
    assert joke_provider.constructor == make_a_joke
    assert joke_provider() == make_a_joke()


def test_provider_class():
    assert isinstance(Provider(Adult)(), Adult)


def test_provider_partial():
    from functools import partial

    provider: Provider = Provider(partial(make_a_joke, joke=orange_joke))
    assert make_a_joke() != provider()
    assert provider() == orange_joke


def test_provider_lambda():
    provider = Provider(lambda: orange_joke)
    assert provider() == orange_joke


def test_provider_with_args():
    expected_constructor = make_a_joke
    provider = Provider(make_a_joke, orange_joke)
    assert provider.constructor == expected_constructor
    assert orange_joke in provider.args
    assert provider.constructor(*provider.args) == provider() == orange_joke


def test_provider_with_kwargs():
    kwargs = {"joke": orange_joke}
    provider = Provider(make_a_joke, **kwargs)
    assert provider.constructor == make_a_joke
    assert provider.keywords == kwargs
    assert provider.constructor(**kwargs) == provider() == orange_joke


def test_provider_compare_equal():
    assert Provider(make_a_joke) == Provider(make_a_joke)
    assert Provider(make_a_joke, orange_joke) == Provider(make_a_joke, orange_joke)
    assert Provider(make_a_joke, joke=orange_joke) == Provider(
        make_a_joke, joke=orange_joke
    )


def test_provider_compare_different():
    assert Provider(make_a_joke) != Provider(make_another_joke)
    assert Provider(make_a_joke, orange_joke) != Provider(make_a_joke, lime_joke)
    assert Provider(make_a_joke, joke=orange_joke) != Provider(
        make_a_joke, joke=lime_joke
    )


def test_provider_can_provide_true():
    assert Provider(make_a_joke).can_provide(str)
    assert Provider(make_a_joke).can_provide(GoodTelling)
    assert Provider(make_a_joke).can_provide(Joke)


def generic_provider(*args) -> list:
    return list(args)


def test_provider_can_provide_generic():
    assert Provider(generic_provider).can_provide(list[int])
    assert Provider(generic_provider).can_provide(list[str])


def test_provider_can_provide_false():
    class StrChild(str): ...

    assert not Provider(make_a_joke).can_provide(int)
    assert not Provider(make_a_joke).can_provide(StrChild)


def test_unknown_provider_call_raises():
    with pytest.raises(UnknownProviderCalled):
        UnknownProvider()


def test_provider_compare_with_wrong_type_raises():
    provider = Provider(lambda: 0)
    with pytest.raises(NotImplementedError):
        assert provider == test_provider_compare_with_wrong_type_raises


def test_provider_class_method_raises():
    with pytest.raises(NotImplementedError):
        Provider(Parent.give_a_good_telling)


def test_provider_local_scope_function_raises():
    def local_function(): ...

    with pytest.raises(NotImplementedError):
        Provider(local_function)


def func_with_union_arg(_: float | str | None) -> int | str:
    return 0


def func_with_explicit_union_arg(_: Union[float, str, None]) -> int | str:  # noqa: UP007
    # Union annotation is used here on purpose here.
    return 0


def func_with_union_return() -> int | str | None:
    return None


def func_with_explicit_union_return() -> Union[int, str, None]:  # noqa: UP007
    # Union annotation is used here on purpose here.
    return None


def test_union_annotation_arg_raises():
    with pytest.raises(NotImplementedError):
        Provider(func_with_union_arg)


def test_explicit_union_annotation_arg_raises():
    with pytest.raises(NotImplementedError):
        Provider(func_with_explicit_union_arg)


def test_union_annotation_return_raises():
    with pytest.raises(NotImplementedError):
        Provider(func_with_union_return)


def test_explicit_union_annotation_return_raises():
    with pytest.raises(NotImplementedError):
        Provider(func_with_explicit_union_return)


def func_without_arg_type(_) -> int:
    return _


def test_insufficient_annotation_raises():
    with pytest.raises(InsufficientAnnotationError):
        Provider(func_without_arg_type)


def test_singleton_provider():
    class TestClass: ...

    singleton_provider = SingletonProvider(TestClass)
    assert singleton_provider() is singleton_provider()


def test_singleton_provider_different_argument_raises():
    class TestClass:
        def __init__(self, arg: int) -> None:
            self.arg = arg

    singleton_provider = SingletonProvider(TestClass)
    assert singleton_provider(arg=0) is singleton_provider(arg=0)
    with pytest.raises(SingletonProviderCalledWithDifferentArgs):
        singleton_provider(arg=1)


def test_singleton_provider_different_argument_handled():
    class TestClass:
        def __init__(self, arg: int) -> None:
            self.arg = arg

    singleton_provider = SingletonProvider(TestClass)
    assert singleton_provider(arg=0) is singleton_provider(arg=0)
    with pytest.raises(SingletonProviderCalledWithDifferentArgs):
        singleton_provider(arg=1)
    assert singleton_provider(arg=0) is singleton_provider(arg=0)


def test_singleton_provider_copied():
    from copy import copy

    class TestClass:
        def __eq__(self, _obj: object) -> bool:
            return isinstance(_obj, TestClass)

    singleton_provider = SingletonProvider(TestClass)
    assert singleton_provider() is not copy(singleton_provider)()
    assert singleton_provider() == copy(singleton_provider)()
