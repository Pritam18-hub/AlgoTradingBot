import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts';

export default function StockChart({ data, ticker }) {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const ema9SeriesRef = useRef(null);
  const ema21SeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const fitDoneRef = useRef(false);

  // Reset the fit flag when the ticker changes
  useEffect(() => {
    fitDoneRef.current = false;
  }, [ticker]);

  // Effect 1: Initialize Chart & Series on ticker change
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create the TradingView Chart instance
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#111622' },
        textColor: '#90a4ae',
        fontFamily: 'Outfit, sans-serif',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.03)' },
      },
      crosshair: {
        mode: 0, // Normal crosshair
        vertLine: { color: '#00b0ff', width: 1, style: 3 },
        horzLine: { color: '#00b0ff', width: 1, style: 3 },
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.08)',
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.08)',
        timeVisible: true,
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
    });

    chartRef.current = chart;

    // Add Candlestick Series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#00e676',
      downColor: '#ff1744',
      borderUpColor: '#00e676',
      borderDownColor: '#ff1744',
      wickUpColor: '#00e676',
      wickDownColor: '#ff1744',
    });
    candleSeriesRef.current = candleSeries;

    // Add Volume Series (overlay)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: 'rgba(0, 176, 255, 0.15)',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '', // Overlay pane
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8, // Place volume at the bottom 20%
        bottom: 0,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    // Add EMA Lines
    const ema9Series = chart.addSeries(LineSeries, {
      color: '#2979ff',
      lineWidth: 1.5,
      title: 'EMA 9',
    });
    ema9SeriesRef.current = ema9Series;

    const ema21Series = chart.addSeries(LineSeries, {
      color: '#ffb300',
      lineWidth: 1.5,
      title: 'EMA 21',
    });
    ema21SeriesRef.current = ema21Series;

    // Resize observer to make chart responsive
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.resize(
          chartContainerRef.current.clientWidth,
          chartContainerRef.current.clientHeight
        );
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        // Safe removal in cleanup
        try {
          chart.remove(candleSeries);
          chart.remove(volumeSeries);
          chart.remove(ema9Series);
          chart.remove(ema21Series);
          chart.destroy();
        } catch (e) {
          console.error("Cleanup error: ", e);
        }
        chartRef.current = null;
      }
    };
  }, [ticker]);

  // Effect 2: Update Series Data when data prop changes
  useEffect(() => {
    if (!chartRef.current || !data || data.length === 0) return;

    // Format data for lightweight-charts
    const candleData = data.map(d => ({
      time: d.time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    const volumeData = data.map(d => ({
      time: d.time,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(0, 230, 118, 0.2)' : 'rgba(255, 23, 68, 0.2)',
    }));

    const ema9Data = data
      .filter(d => d.ema_9 !== null && d.ema_9 !== undefined)
      .map(d => ({ time: d.time, value: d.ema_9 }));

    const ema21Data = data
      .filter(d => d.ema_21 !== null && d.ema_21 !== undefined)
      .map(d => ({ time: d.time, value: d.ema_21 }));

    // Set series data with checks
    if (candleSeriesRef.current) candleSeriesRef.current.setData(candleData);
    if (volumeSeriesRef.current) volumeSeriesRef.current.setData(volumeData);
    
    if (ema9SeriesRef.current) {
      if (ema9Data.length > 0) ema9SeriesRef.current.setData(ema9Data);
      else ema9SeriesRef.current.setData([]);
    }
    
    if (ema21SeriesRef.current) {
      if (ema21Data.length > 0) ema21SeriesRef.current.setData(ema21Data);
      else ema21SeriesRef.current.setData([]);
    }

    // Only fit content once per ticker to preserve zoom on periodic polls
    if (chartRef.current && !fitDoneRef.current) {
      chartRef.current.timeScale().fitContent();
      fitDoneRef.current = true;
    }
  }, [data]);

  return <div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />;
}
