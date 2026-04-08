import Choices from 'choices.js'
import {
  area,
  axisBottom,
  axisLeft,
  create,
  curveBumpX,
  extent,
  line,
  scaleLinear,
  scaleUtc,
  schemeTableau10
} from 'd3'

function setupChart(container, data, config) {
  function setupSearch(input) {
    const addItemText = input.dataset.additemtext ?? ''
    const loadingText = input.dataset.loading ?? ''
    const noResultsText = input.dataset.noresults ?? ''
    const noChoicesText = input.dataset.nochoices ?? ''
    const itemSelectText = input.dataset.itemselect ?? ''
    const uniqueItemText = input.dataset.uniqueitemtext ?? ''
    const fetchUrl = input.dataset.fetchurl ?? ''
    const queryParam = config.queryparam ?? 'q'

    const choices = new Choices(input, {
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
      uniqueItemText,
      callbackOnInit: () => update()
    })

    input.addEventListener('addItem', (e) => {
      const value = e.detail.value
      fetchData(value)
    })

    input.addEventListener('removeItem', (e) => {
      const value = e.detail.value
      data.facets = data.facets.filter((d) => d.term !== value)
      const color = colorMap.get(value)
      if (color !== undefined) {
        availableColors.unshift(color)
        colorMap.delete(value)
      }
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
          if (!choices.getValue(true).includes(term)) {
            return
          }
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

  const toDate = (d) => new Date(d)

  // Declare the x (horizontal position) scale.
  const x = scaleUtc()
    .domain(extent(baseline, (d) => toDate(d[0])))
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

  const yFunc = (d) => y((d.count / baselineMapping.get(d.key)) * 100)

  const chartArea = area()
    .curve(curveBumpX)
    .x((d) => x(toDate(d.key)))
    .y0(y(0))
    .y1(yFunc)

  const chartLine = line()
    .curve(curveBumpX)
    .x((d) => x(toDate(d.key)))
    .y(yFunc)

  const pathElements = svg.append('g')
  const colorMap = new Map()
  const color = (d) => colorMap.get(d)
  const availableColors = [...schemeTableau10]

  function update() {
    data.facets.forEach((d) => {
      if (!colorMap.has(d.term)) {
        colorMap.set(d.term, availableColors.shift())
      }
      const termNode = container.querySelector(
        `.choices__item[data-value="${d.term.replace(/"/g, '\\"')}"]`
      )
      if (termNode) {
        termNode.style.backgroundColor = color(d.term)
      }
    })

    const flatData = []
    data.facets.forEach((facet) => {
      facet.date.forEach((date) => {
        flatData.push({
          term: facet.term,
          ...date
        })
      })
    })
    const idFunc = function (d) {
      return d ? d.term : this.id
    }

    const fillPaths = pathElements
      .selectAll('path.fill')
      .data(data.facets, idFunc)
    fillPaths
      .enter()
      .append('path')
      .attr('class', 'fill')
      .attr('fill', (d) => color(d.term))
      .attr('fill-opacity', 0.3)
      .attr('d', (d) => chartArea(d.date))
      .append('title')
      .text((d) => d.term)
    fillPaths.exit().remove()

    const strokePaths = pathElements
      .selectAll('path.stroke')
      .data(data.facets, idFunc)
    strokePaths
      .enter()
      .append('path')
      .attr('class', 'stroke')
      .attr('stroke', (d) => color(d.term))
      .attr('stroke-width', 4)
      .attr('fill', 'transparent')
      .attr('d', (d) => chartLine(d.date))
      .append('title')
      .text((d) => d.term)
    strokePaths.exit().remove()

    const dots = pathElements.selectAll('circle').data(flatData, idFunc)
    dots
      .enter()
      .append('circle')
      .on('click', (_e, d) => {
        if (config.searchUrl) {
          const after = new Date(d.key)
          let before
          if (config.interval === 'month') {
            before = new Date(after.getFullYear(), after.getMonth() + 1, 0)
          } else if (config.interval === 'week') {
            before = new Date(after.getTime() + 6 * 24 * 60 * 60 * 1000)
          } else {
            before = new Date(after.getFullYear(), 11, 31)
          }
          const params = new URLSearchParams({
            q: d.term,
            [`${config.dateparam}_after`]: `${d.key}`,
            [`${config.dateparam}_before`]: `${before.getFullYear()}-${String(before.getMonth() + 1).padStart(2, '0')}-${String(before.getDate()).padStart(2, '0')}`
          })
          window.open(`${config.searchUrl}?${params.toString()}`)
        }
      })
      .attr('fill', (d) => color(d.term))
      // .attr("stroke-width", 2)
      // .attr("fill", "transparent")
      .attr('cx', (d) => x(toDate(d.key)))
      .attr('cy', yFunc)
      .attr('r', 5)
      .attr('style', 'cursor:pointer')
      .attr('title', (d) => d.term)
    dots.exit().on('click', null).remove()
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
  const facetCharts = document.querySelectorAll('[data-datefacetchart]')

  facetCharts.forEach((chart) => {
    const data = JSON.parse(chart.querySelector('script').textContent)
    setupChart(chart, data, {
      searchUrl: chart.dataset.searchurl,
      queryparam: chart.dataset.queryparam,
      dateparam: chart.dataset.dateparam,
      interval: chart.dataset.interval
    })
  })
})
