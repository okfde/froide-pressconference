import Choices from 'choices.js'
import {
  area,
  axisBottom,
  axisLeft,
  create,
  curveCatmullRom,
  extent,
  line,
  scaleLinear,
  scaleUtc,
  schemeTableau10
} from 'd3'

function setupChart(container, data) {
  function setupSearch(input) {
    const addItemText = input.dataset.additemtext ?? ''
    const loadingText = input.dataset.loading ?? ''
    const noResultsText = input.dataset.noresults ?? ''
    const noChoicesText = input.dataset.nochoices ?? ''
    const itemSelectText = input.dataset.itemselect ?? ''
    const uniqueItemText = input.dataset.uniqueitemtext ?? ''
    const fetchUrl = input.dataset.fetchurl ?? ''
    const queryParam = input.dataset.queryparam ?? 'q'

    new Choices(input, {
      addItemText(value) {
        return addItemText.replace('${value}', value)
      },
      addItems: true,
      delimiter: ',',
      duplicateItemsAllowed: false,
      editItems: true,
      maxItemCount: schemeTableau10.length,
      itemSelectText,
      loadingText,
      noChoicesText,
      noResultsText,
      searchResultLimit: 0,
      removeItemButton: true,
      uniqueItemText
    })

    input.addEventListener('addItem', (e) => {
      const value = e.detail.value
      fetchData(value)
    })

    input.addEventListener('removeItem', (e) => {
      const value = e.detail.value
      data.facets = data.facets.filter((d) => d.term !== value)
      const color = colorMap.get(value)
      availableColors.unshift(color)
      colorMap.delete(value)
      update()
    })

    function fetchData(term) {
      if (fetchUrl === '') {
        return
      }
      const url = new URL(fetchUrl, window.location.origin)
      url.searchParams.set(queryParam, term)
      fetch(url.href)
        .then((response) => response.json())
        .then((response) => {
          console.log(response)
          data.facets = [...data.facets, ...response.facets]
          update()
        })
    }
    return {
      fetchData
    }
  }

  const baseline = data.baseline
  const baselineMapping = new Map(baseline)

  const width = container.offsetWidth
  const height = 300
  const marginTop = 20
  const marginRight = 20
  const marginBottom = 30
  const marginLeft = 40

  const yearToDate = (d) => new Date(`${d}-01-01`)

  // Declare the x (horizontal position) scale.
  const x = scaleUtc()
    .domain(extent(baseline, (d) => yearToDate(d[0])))
    .range([marginLeft, width - marginRight])

  // Declare the y (vertical position) scale.
  const y = scaleLinear()
    .domain([0, 100])
    .range([height - marginBottom, marginTop])

  // Create the SVG container.
  const svg = create('svg').attr('width', width).attr('height', height)

  // Add the x-axis.
  svg
    .append('g')
    .attr('transform', `translate(0,${height - marginBottom})`)
    .call(axisBottom(x))

  // Add the y-axis.
  svg
    .append('g')
    .attr('transform', `translate(${marginLeft},0)`)
    .call(axisLeft(y).tickFormat((d) => d + '%'))

  const yFunc = (d) => y((d.count / baselineMapping.get(+d.key)) * 100)

  const chartArea = area()
    .curve(curveCatmullRom)
    .x((d) => x(yearToDate(d.key)))
    .y0(y(0))
    .y1(yFunc)

  const chartLine = line()
    .curve(curveCatmullRom)
    .x((d) => x(yearToDate(d.key)))
    .y(yFunc)

  const style = document.createElement('style')
  document.head.appendChild(style)

  const pathElements = svg.append('g')
  let pathData = pathElements.selectAll('g')
  const colorMap = new Map()
  const color = (d) => colorMap.get(d)
  const availableColors = [...schemeTableau10]

  function update() {
    data.facets.forEach((d) => {
      if (!colorMap.has(d.term)) {
        colorMap.set(d.term, availableColors.shift())
      }
    })
    style.innerText = data.facets
      .map(
        (d) => `.choices__item[data-value="${d.term.replace(/"/g, '')}"] {
            background-color: ${color(d.term)};
        }`
      )
      .join('\n')

    // Append a path for each series.
    pathData = pathElements.selectAll('g').data(data.facets, function (d) {
      console.log(d, d.term, this.id)
      return d ? d.term : this.id
    })

    const pathGroup = pathData.enter().append('g')

    pathGroup
      .append('path')
      .attr('fill', (d) => color(d.term))
      .attr('fill-opacity', 0.3)
      .attr('d', (d) => chartArea(d.date))
      .append('title')
      .text((d) => d.term)
    pathGroup
      .append('path')
      .attr('stroke', (d) => color(d.term))
      .attr('stroke-width', 4)
      .attr('fill', 'transparent')
      // .attr("fill-opacity", 0.3)
      .attr('d', (d) => chartLine(d.date))
      .append('title')
      .text((d) => d.term)

    pathGroup
      .selectAll('circle')
      .data((d) => d.date.map((x) => ({ term: d.term, ...x })))
      .enter()
      .append('circle')
      .attr('fill', (d) => color(d.term))
      // .attr("stroke-width", 2)
      // .attr("fill", "transparent")
      .attr('cx', (d) => x(yearToDate(d.key)))
      .attr('cy', yFunc)
      .attr('r', 5)
      .attr('title', (d) => d.term)

    pathData.exit().remove().remove()
  }

  update()
  container.append(svg.node())

  const input = container.querySelector('input')
  if (input) {
    setupSearch(input)
  }
}

// Append the SVG element.
document.addEventListener('DOMContentLoaded', () => {
  const data = JSON.parse(document.getElementById('facet-data').textContent)
  const facetCharts = document.querySelectorAll('[data-datefacetchart]')

  facetCharts.forEach((chart) => {
    setupChart(chart, data)
  })
})
