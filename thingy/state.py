import dataclasses
from typing import Union, Any
from lxml.objectify import ObjectifiedElement
from thingy.collections import Report
from thingy.collections import FallThruDict, Date
from collections import defaultdict
from icecream import ic
from thingy.metric_handlers import Fact, Ratio


@dataclasses.dataclass(frozen=True)
class ResultKey:
    period: str
    symbol: str
    year: int
    quarter: int


@dataclasses.dataclass
class ResultValue:
    facts: dict[str, float]
    ratios: dict[str, Ratio.Metric]


@dataclasses.dataclass
class Metadata:
    facts: dict[str, list[Fact]]
    ratios: dict[str, list[Ratio]]
    symbols: list[str]
    dates: list[Date]

    def __bool__(self):
        return all(self.__dict__.values())


@dataclasses.dataclass
class DeferredEval:
    fact: Fact
    eval: ObjectifiedElement


@dataclasses.dataclass
class State:
    # Index into result
    period: str = None
    symbol: str = None
    date: Date = None

    # Temporary data
    deferred_evals: list[DeferredEval] = dataclasses.field(default_factory=list)
    report: Report = None
    fact: Fact = None

    # Long-term storage
    result: dict[ResultKey, ResultValue] = dataclasses.field(
        default_factory=lambda: defaultdict(
            lambda: ResultValue(facts=dict(), ratios=dict())))
    metadata: Metadata = dataclasses.field(
        default_factory=lambda: Metadata(
            facts=defaultdict(dict),
            ratios=defaultdict(dict),
            symbols=None,
            dates=None))

    def __bool__(self) -> bool:
        return all((self.result, self.metadata))

    def to_dict(self) -> dict:
        return self.__dict__

    @property
    def key(self) -> ResultKey:
        if not all((self.period, self.symbol, self.date)):
            ic(self)
            raise ValueError('Unable to create key')
        return ResultKey(period=self.period,
                         symbol=self.symbol,
                         year=self.date.year,
                         quarter=self.date.quarter)

    @property
    def current_result(self) -> ResultValue:
        return self.result[self.key]
