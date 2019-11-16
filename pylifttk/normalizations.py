
import typing as _typing

import pylifttk


normalizations = pylifttk.config["normalizations"].get()


def _find_normalization_path(src, dst):
    # type: (str, str) -> _typing.Optional[_typing.List[str]]
    """


    :param src:
    :param dst:
    :return:
    """
    # Build a graph of the normalizations

    graph = {}

    for normalization in normalizations:
        src = normalization["source"]
        dst = normalization["destination"]

        # Add bidirectional edge to graph
        graph[src] = graph.get(src, list()) + [dst]
        graph[dst] = graph.get(dst, list()) + [src]

    def dfs(start, end, path=None):
        # type: (str, str, _typing.Optional[_typing.List[str]]) -> _typing.Optional[_typing.List[str]]
        if start == end:
            return path + [end]

        if path is None:
            path = list()
        elif start in path:
            return
        path = path + [start]

        possibilities = graph.get(start, list())

        for p in possibilities:
            ret_path = dfs(p, end, path=path)
            if ret_path is not None:
                return ret_path

    return dfs(start=src, end=dst)


def normalize(word, src, dst, echo_word=False):
    # type: (str, str, str, bool) -> _typing.Optional[str]
    """

    :param word:
    :param src:
    :param dst:
    :param echo_word:
    :return:
    """

    def apply_direct_normalization(word, src, dst):
        # type: (str, str, str) -> _typing.Optional[str]
        for normalization in normalizations:

            # Direct lookup
            if (src == normalization["source"] and
                    dst == normalization["destination"]):

                return normalization["mapping"].get(word)

            # Reverse lookup
            elif (dst == normalization["source"] and
                  src == normalization["destination"]):

                for key, value in normalization["mapping"].items():
                    if value == word:
                        return key

    normalization_path = _find_normalization_path(src, dst)
    if normalization_path is None:
        return

    result = word
    for i in range(len(normalization_path) - 1):
        src = normalization_path[i]
        dst = normalization_path[i + 1]
        result = apply_direct_normalization(result, src, dst)

    if result is None and echo_word:
        return word

    return result
