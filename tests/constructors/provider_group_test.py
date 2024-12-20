# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
from typing import NewType

import pytest

from appstract.constructors import (
    ConflictProvidersError,
    MismatchingProductTypeError,
    Provider,
    ProviderExistsError,
    ProviderGroup,
    ProviderNotFoundError,
    SingletonProvider,
)
from appstract.constructors._test_helpers import (
    GoodTelling,
    Joke,
    give_a_good_telling,
    lime_joke,
    make_a_joke,
    make_another_joke,
    orange_joke,
)


def test_provider_setitem():
    provider_group = ProviderGroup()
    provider_group[Joke] = make_a_joke
    assert provider_group[Joke].constructor == make_a_joke
    assert provider_group[Joke]() == make_a_joke()


def test_provider_values():
    provider_group = ProviderGroup()
    provider_group[str] = str
    provider_group[Joke] = make_a_joke
    assert Provider(str) in provider_group.values()
    assert Provider(make_a_joke) in provider_group.values()


def test_provider_items():
    provider_group = ProviderGroup()
    provider_group[str] = make_a_joke
    provider_group[int] = lambda: 0
    for product_type, provider in provider_group.items():
        isinstance(provider(), product_type)


def test_provider_already_exists_raises():
    provider_group = ProviderGroup()
    provider_group[Joke] = make_a_joke
    with pytest.raises(ProviderExistsError):
        provider_group[Joke] = make_another_joke


def test_provider_group_add():
    funny = ProviderGroup(make_a_joke)
    grumpy = ProviderGroup(give_a_good_telling)
    neutral = funny + grumpy
    assert neutral[Joke]() == funny[Joke]()
    assert neutral[GoodTelling]() == grumpy[GoodTelling]()


def test_provider_group_add_wrong_type_raises():
    funny = ProviderGroup(make_a_joke)
    with pytest.raises(NotImplementedError):
        funny + GoodTelling


def test_provider_group_clear_all():
    provider_group = ProviderGroup()
    provider_group[int] = lambda: 99
    assert provider_group[int]() == 99
    provider_group.clear()
    with pytest.raises(ProviderNotFoundError, match="int"):
        provider_group[int]
    assert len(provider_group) == 0


def test_mismatching_type_provider_raises():
    provider_group = ProviderGroup()
    with pytest.raises(MismatchingProductTypeError):
        provider_group[None] = make_a_joke  # type: ignore[index]

    WrongType = NewType("WrongType", int)
    with pytest.raises(MismatchingProductTypeError, match="WrongType"):
        provider_group[WrongType] = make_a_joke


def test_providers_conflicting_but_sharable():
    funny = ProviderGroup(make_a_joke)
    just_funny = funny + funny
    assert just_funny[Joke]() == funny[Joke]()
    assert len(just_funny) == len(funny)


def test_providers_conflicting_providers_raises():
    funny = ProviderGroup(make_a_joke)
    funnier = ProviderGroup(make_another_joke)
    with pytest.raises(ConflictProvidersError):
        funny.merge(funnier)


def test_providers_merge_conflicting_args_raises():
    funny = ProviderGroup()
    funnier = ProviderGroup()
    funny.provider(Provider(make_a_joke, lime_joke))
    funnier.provider(Provider(make_a_joke, orange_joke))
    with pytest.raises(ConflictProvidersError):
        funny.merge(funnier)


def test_providers_merge_conflicting_keywords_raises():
    funny = ProviderGroup()
    funnier = ProviderGroup()
    funny.provider(Provider(make_a_joke, joke=lime_joke))
    funnier.provider(Provider(make_a_joke, joke=orange_joke))
    with pytest.raises(ConflictProvidersError):
        funny.merge(funnier)


def singleton_function() -> ProviderGroup:
    return ProviderGroup()


def test_singleton_provider_function():
    provider_gr = ProviderGroup()
    provider_gr.provider(singleton_function, provider_type=SingletonProvider)
    first_instance = provider_gr[ProviderGroup]()
    second_instance = provider_gr[ProviderGroup]()
    assert first_instance is second_instance


def test_singleton_provider_initially_registered():
    provider_gr = ProviderGroup(SingletonProvider(singleton_function))
    first_instance = provider_gr[ProviderGroup]()
    second_instance = provider_gr[ProviderGroup]()
    assert first_instance is second_instance


def test_singleton_provider_registered_by_setter():
    provider_gr = ProviderGroup()
    provider_gr[ProviderGroup] = SingletonProvider(singleton_function)
    first_instance = provider_gr[ProviderGroup]()
    second_instance = provider_gr[ProviderGroup]()
    assert first_instance is second_instance


def test_singleton_provider_registered_with_type_changed():
    provider_gr = ProviderGroup()
    original_provider = SingletonProvider(singleton_function)
    provider_gr.provider(original_provider, provider_type=Provider)
    assert isinstance(provider_gr[ProviderGroup], Provider)
    assert not isinstance(provider_gr[ProviderGroup], SingletonProvider)
    first_instance = provider_gr[ProviderGroup]()
    second_instance = provider_gr[ProviderGroup]()
    assert first_instance is not second_instance


def test_singleton_provider_function_copied():
    provider_gr = ProviderGroup()
    provider_gr.provider(singleton_function, provider_type=SingletonProvider)
    new_gr = ProviderGroup()
    new_gr.merge(provider_gr)

    assert provider_gr[ProviderGroup]() is not new_gr[ProviderGroup]()
