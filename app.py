import datetime
import thingy.engine
import lxml.objectify
from mako.template import Template
from thingy.collections import Date

import logging
logging.basicConfig(level=logging.DEBUG)

reports = (
    ('CDEV', 'MTDR', 'QEP', 'SM', 'NR', 'XOM', 'CVX', 'GEL', 'FET', 'CPE'),
    ('ABEPF', 'ARXRF', 'FTSSF', 'NMTLF', 'DCNNF', 'ALLIF', 'CCWOF', 'LTUM', 'FUSEF'),
)

dates = {
    'quarterly': [Date(year, quarter)
                  for year in (2019, 2020)
                  for quarter in (1, 2, 3, 4)],
    'annual': [Date(year, 0)
               for year in (2016, 2017, 2018, 2019, 20220)]
}

# reports = [('CDEV', 'MTDR')]
# dates = {
#     'quarterly': [Date(2020, 4), Date(2020, 3)],
#     'annual': [Date(2020, 0), Date(2019, 0)]
# }

for symbols in reports:
    with open('thingy/engine.xml') as f:
        engine = thingy.engine.Engine(
            symbols=symbols,
            logic=lxml.objectify.fromstring(f.read()),
            template_engine=Template(filename='thingy/templates/template.html.mako')
        )

    engine.execute(dates).write(
        f'/home/pnaudus/Downloads/{datetime.date.today()} - Comparative analysis of {"-".join(engine.symbols)}.html')
