import py_expression_eval
from lxml.objectify import ObjectifiedElement
from typing import Any, Optional
from icecream import ic
from thingy.collections import Report, Date
from dataclasses import dataclass


class CashedExpressionParser(py_expression_eval.Parser):

    CACHE = dict()

    def parse(self, expression: str) -> py_expression_eval.Expression:
        if expression not in self.CACHE:
            self.CACHE[expression] = super().parse(expression)
        return self.CACHE[expression]

    def evaluate(self, expression: str, variables: dict) -> Any:
        return self.parse(expression).evaluate(variables)

    def variables(self, expression: str) -> list:
        return self.parse(str(expression)).variables()


class Fact:

    expression_parser = CashedExpressionParser()

    def __init__(self, fact: ObjectifiedElement):
        self.fact = fact
        self.id = fact.get('id')
        self.label = fact.get('label', fact.get('id').replace('_', ' ').title())

    def execute_eval(self, eval: ObjectifiedElement, fact_context: dict[str, float]) -> float:
        try:
            return self.expression_parser.evaluate(eval, fact_context)
        except BaseException as e:
            ic(eval)
            ic(fact_context)
            raise

    def eval_has_prerequisites(self, eval: ObjectifiedElement, fact_context: dict[str, float]) -> bool:
        variables = self.expression_parser.variables(eval)
        if missing := (set(variables) - set(fact_context)):
            ic(f'The following variables have not yet been defined: {missing}. Deferring')
            return False
        return True

    def execute_query(self, query: ObjectifiedElement, report_data: Report) -> Optional[float]:

        if (result := self._compute_query(query, report_data)):
            return self._compute_query_post(result, query)

    @staticmethod
    def _compute_query(query: ObjectifiedElement, report_data: Report) -> list:

        if not (source := getattr(report_data, query.get('source'), None)):
            raise ValueError(f'Unknown source: {query.get("source")}')

        payload = [line.strip() for line in str(query).split('\n')]

        if query.get('mode') == 'select':
            return source.get_all(*payload)
        elif query.get('mode') == 'regexp':
            return source.search(*payload)

        raise ValueError(f'Unsupported mode: {query.get("mode")}')

    @staticmethod
    def _compute_query_post(compute_result: list,
                            query: ObjectifiedElement) -> float:

        if not query.get('post'):
            return compute_result[0]

        if query.get('post') == 'sum':
            return sum(compute_result)
        elif query.get('post') == 'static':
            return float(query.get('value'))
        else:
            raise ValueError(f'Unsupported post: {query.get("post")}')


class Ratio:

    expression_parser = CashedExpressionParser()

    @dataclass
    class Metric:
        a: float
        b: float
        ratio: float

    @dataclass
    class Sources:
        a: str
        b: str

    def __init__(self, ratio: ObjectifiedElement):
        self.id = ratio.get('id')
        self.label = ratio.get('label', ratio.get('id').replace('_', ' ').title())
        self.description = next(ratio.itertext()).strip()
        self.source = self.Sources(
            a=ratio.compute.get('source.a'),
            b=ratio.compute.get('source.b')
        )

    @classmethod
    def calculate_ratio(cls, ratio: ObjectifiedElement, fact_context: dict[str, float]) -> Metric:
        try:
            A = cls.calculate_compute(ratio.compute.get('source.a'), fact_context)
            B = cls.calculate_compute(ratio.compute.get('source.b'), fact_context)
        except BaseException:
            ic(ratio.get('id'))
            ic(ratio.compute.get('source.a'))
            ic(ratio.compute.get('source.b'))
            ic(fact_context)
            raise
        return cls.Metric(a=A, b=B, ratio=A / B)

    @classmethod
    def calculate_compute(cls, statement: str, fact_context: dict[str, float]):
        if statement in fact_context:
            return fact_context[statement]
        return cls.expression_parser.evaluate(statement, fact_context)
