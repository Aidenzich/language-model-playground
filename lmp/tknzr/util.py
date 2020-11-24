import re
import typing
import unicodedata
from typing import List, Optional, Sequence


def norm(txt: str) -> str:
    r"""Perform normalization on Text.

    Text will first be :term:`NFKC` normalized, then convert consecutive
    whitespaces into single whitespace. Both leading and trailing whitespaces
    will be stripped.

    Parameters
    ==========
    txt : str
        Text to be normalized.

    Returns
    =======
    str
        Normalized text.

    Examples
    ========
    >>> from lmp.tknzr.util import norm
    >>> norm('１２３４５６７８９')
    '123456789'
    """
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', txt).strip())


@typing.overload
def trunc_to_max(
        seq: Sequence[int],
        *,
        max_seq_len: Optional[int] = -1,
) -> List[int]:
    ...


@typing.overload
def trunc_to_max(
        seq: Sequence[str],
        *,
        max_seq_len: Optional[int] = -1,
) -> List[str]:
    ...


def trunc_to_max(seq, *, max_seq_len=-1):
    r"""Truncate sequence when sequence is longer than allowed.

    Truncate trailing sequence to satisfy maximum sequence length constraint.
    When ``max_seq_len == -1`` or sequence is not longer than ``max_seq_len``,
    do nothing and return the original sequence.
    Otherwise return truncated sequence.

    Sequence can be either a list of integer or a list of string.

    Arguments
    =========
    seq: Union[int, str]
        Sequence to be truncated.
    max_seq_len: int, optional
        Maximum sequence length constraint.
        Defaults to ``-1``.

    Returns
    =======
    Union[int, str]
        Truncated sequence.

    See Also
    ========
    lmp.tknzr.util.pad_to_max

    Examples
    ========
    >>> from lmp.tknzr.util import trunc_to_max
    >>> trunc_to_max(['a', 'b', 'c'], max_seq_len=2)
    ['a', 'b']
    >>> trunc_to_max(['a', 'b', 'c'], max_seq_len=3)
    ['a', 'b', 'c']
    >>> trunc_to_max(['a', 'b', 'c'], max_seq_len=4)
    ['a', 'b', 'c']
    >>> trunc_to_max(['a', 'b', 'c'], max_seq_len=-1)
    ['a', 'b', 'c']
    >>> trunc_to_max([1, 2, 3], max_seq_len=1)
    [1]
    >>> trunc_to_max([1, 2, 3], max_seq_len=-1)
    [1, 2, 3]
    """
    if max_seq_len == -1:
        return seq
    # Truncate sequence to maximum sequence length.
    return seq[:max_seq_len]


@typing.overload
def pad_to_max(
        seq: Sequence[int],
        pad: int,
        *,
        max_seq_len: Optional[int] = -1,
) -> List[int]:
    ...


@typing.overload
def pad_to_max(
        seq: Sequence[str],
        pad: str,
        *,
        max_seq_len: Optional[int] = -1,
) -> List[str]:
    ...


def pad_to_max(seq, pad, *, max_seq_len=-1):
    r"""Pad sequence when sequence is shorter than required.

    Add padding ``pad`` at the end of sequence until satisfying maximum
    sequence length constraint.
    When ``max_seq_len == -1`` or sequence is not shorter than ``max_seq_len``,
    do nothing and return the original sequence.
    Otherwise return padded sequence.

    Sequence can be either a list of integer or a list of string.
    When ``seq`` is a list of integer, ``pad`` must also be integer;
    When ``seq`` is a list of string, ``pad`` must also be string.

    Arguments
    =========
    seq: Union[int, str]
        Sequence to be padded.
    pad: Union[int, str]
        Padding to be add at the end of sequence.
    max_seq_len: int, optional
        Maximum sequence length constraint.
        Defaults to ``-1``.

    Returns
    =======
    Union[int, str]
        Padded sequence.

    See Also
    ========
    lmp.tknzr.util.trunc_to_max

    Examples
    ========
    >>> from lmp.tknzr.util import pad_to_max
    >>> pad_to_max(['a', 'b', 'c'], 'p', max_seq_len=4)
    ['a', 'b', 'c', 'p']
    >>> pad_to_max(['a', 'b', 'c'], 'p', max_seq_len=3)
    ['a', 'b', 'c']
    >>> pad_to_max(['a', 'b', 'c'], 'p', max_seq_len=2)
    ['a', 'b', 'c']
    >>> pad_to_max(['a', 'b', 'c'], max_seq_len=-1)
    ['a', 'b', 'c']
    >>> pad_to_max([1, 2, 3], 0, max_seq_len=5)
    [1, 2, 3, 0, 0]
    >>> pad_to_max([1, 2, 3], max_seq_len=-1)
    [1, 2, 3]
    """
    if max_seq_len == -1:
        return seq

    # Calculate padding length.
    pad_len = max(0, max_seq_len - len(seq))

    # Pad to maximum sequence length.
    return seq + [pad] * pad_len
