<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<%
  ratio_color_a = 'orange'
  ratio_color_b = 'purple'
%>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://cdn.simplecss.org/simple.min.css">
  <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/v/ju-1.12.1/jq-3.3.1/dt-1.10.23/cr-1.5.3/fh-3.1.8/rr-1.2.7/datatables.min.css"/>
  <title>
    Comparative analysis of ${metadata.symbols} :: Market Thingy
  </title>
  <script type="text/javascript" src="https://cdn.datatables.net/v/ju-1.12.1/jq-3.3.1/dt-1.10.23/cr-1.5.3/fh-3.1.8/rr-1.2.7/datatables.min.js"></script>
  <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/jquery-sparklines/2.1.2/jquery.sparkline.min.js"></script>
  <script type="text/javascript">
    $(document).ready(function() {
      $('.sparkline.bar').sparkline('html', {
        type: 'bar', 
        barWidth: 10, 
        barSpacing: 1,
        tooltipPrefix: '$',
        stackedBarColor: ['orange', 'purple']});
      $('.sparkline.pie').sparkline('html', {
        type: 'pie',
        sliceColors: ['${ratio_color_a}', '${ratio_color_b}']});
      $('table').DataTable({
        colReorder: true,
        rowReorder: {selector: 'tr'},
        ordering: true,
        paging: false,
        searching: false,
        fixedHeader: true
      });
      $('#tabs').tabs();
    });
  </script>

  <style type="text/css">
    .sparkline { display: block; }
    .source { font-size: x-small; }
    .source span { padding-right: 0.5em; }
    .source.a span { color: ${ratio_color_a}; }
    .source.b span { color: ${ratio_color_b}; }
    main { max-width: 85rem; }
  </style>
</head>
<body>
  <header>
    This is a comparative analysis of the following stocks:

    <ul>
      %for symbol in metadata.symbols:
        <li>${symbol}</li>
      %endfor
    </ul>
  </header>

  <main>
    <h1>Facts</h1>

    <div id='tabs'>
      <ul>
        %for period in ['quarterly', 'annual']:
          <li><a href='#tabs-${period}-reports'>${period.title()} Reports</a></li>
        %endfor
      </ul>

      %for period in ['quarterly', 'annual']:
        <div id='tabs-${period}-reports'>

          %for fact_group, facts in metadata.facts.items():
            <h2>${fact_group} (${period.title()})</h2>
            <table>
              <thead>
                <tr>
                  <td></td>
                  %for fact in facts:
                    <th>${fact.label}</th>
                  %endfor

                </tr>
              </thead>
              <tbody>
                %for symbol in metadata.symbols:
                  <tr>
                    <th>${symbol}</th>
                    %for fact in facts:
                      <td>
                        <%
                        key = ResultKey(period=period,
                                symbol=symbol,
                                year=metadata.dates[period][-1].year,
                                quarter=metadata.dates[period][-1].quarter)
                        %>
                        $${f'{result[key].facts[fact.id]:,}'}
                        <span class="sparkline bar facts">
                        <%
                          values = list()
                          for date in metadata.dates[period]:
                            key = ResultKey(period=period,
                                    symbol=symbol,
                                    year=date.year,
                                    quarter=date.quarter)
                            if key in result:
                              values.append(str(int(result[key].facts[fact.id])))
                        %>
                        ${','.join(values)}
                        </span>
                      </td>
                    %endfor
                  </tr>
                %endfor
              </tbody>
            </table>
          %endfor

          <h1>Ratios</h1>

          %for ratio_group, ratios in metadata.ratios.items():
            <h2>${ratio_group} (${period.title()})</h2>

            <blockquote>
              <h3>Definitions</h3>
              <ul>
              %for ratio in ratios:
                <li><b>${ratio.label}</b> - ${ratio.description}</li>
              %endfor
              </ul>
            </blockquote>

            <table>
              <thead>
                <tr>
                  <td></td>
                  %for ratio in ratios:
                    <th>
                      ${ratio.label}
                      <div class="source a"><span>&#9679;</span>${ratio.source.a}</div>
                      <div class="source b"><span>&#9679;</span>${ratio.source.b}</div>
                    </th>
                  %endfor
                </tr>
              </thead>
              <tbody>
                %for symbol in metadata.symbols:
                  <tr>
                    <th>${symbol}</th>
                    %for ratio in ratios:
                      <td>
                        <%
                        key = ResultKey(period=period,
                                symbol=symbol,
                                year=metadata.dates[period][-1].year,
                                quarter=metadata.dates[period][-1].quarter)
                        %>
                        ${f'{result[key].ratios[ratio.id].ratio:.2f}'}
                        <span class="sparkline pie ratio">
                        ${result[key].ratios[ratio.id].a}, ${result[key].ratios[ratio.id].b}
                        </span>
                        <span class="sparkline bar ratio">
                          <%
                          values = list()
                          for date in metadata.dates[period]:
                            key = ResultKey(period=period,
                                    symbol=symbol,
                                    year=date.year,
                                    quarter=date.quarter)
                            if key in result:
                              values.append(
                                ':'.join((
                                  str(result[key].ratios[ratio.id].a),
                                  str(result[key].ratios[ratio.id].b)
                                ))
                            )
                          %>
                          ${','.join(values)}
                        </span>
                      </td>
                    %endfor
                  </tr>
                %endfor
              </tbody>
            </table>
          %endfor
        </div>
      %endfor
  </main>

  <footer>
    <%
    import datetime
    %>
    This file was generated by MarketThingy at ${datetime.datetime.now().isoformat()}
  </footer>
</body>
</html>
