/** Factor (feature) Chinese-name mapping and tooltips. */

export interface FeatureMeta {
  cn: string
  desc: string
  formula?: string
}

export const FEATURE_LABELS: Record<string, FeatureMeta> = {
  rsi_14: { cn: '14日相对强弱指数', desc: '衡量超买超卖状态', formula: '100 - 100/(1+RS)' },
  macd: { cn: 'MACD', desc: '快慢均线差', formula: 'EMA12 - EMA26' },
  macd_signal: { cn: 'MACD信号线', desc: 'MACD的9日EMA' },
  macd_hist: { cn: 'MACD柱', desc: 'MACD与信号线差值' },
  ma_5: { cn: '5日均线', desc: '近5日收盘均价' },
  ma_20: { cn: '20日均线', desc: '近20日收盘均价' },
  ma_60: { cn: '60日均线', desc: '近60日收盘均价' },
  close_to_ma_20: { cn: '收盘偏离20日线', desc: '收盘价相对20日均线的偏离度' },
  ma5_to_ma20: { cn: '5/20日均线叉', desc: '短期均线相对中期均线' },
  return_1d: { cn: '1日收益', desc: '昨日涨跌幅' },
  return_5d: { cn: '5日收益', desc: '近5日涨跌幅' },
  return_20d: { cn: '20日收益', desc: '近20日涨跌幅' },
  volatility_20d: { cn: '20日波动率', desc: '日收益标准差' },
  volatility_60d: { cn: '60日波动率', desc: '日收益标准差' },
  atr_14: { cn: '14日ATR', desc: '平均真实波幅' },
  atr_ratio: { cn: 'ATR比率', desc: 'ATR/收盘价' },
  volume_ratio_5: { cn: '5日量比', desc: '当日量/5日均量' },
  volume_ratio_20: { cn: '20日量比', desc: '当日量/20日均量' },
  avg_amount_20d: { cn: '20日均成交额', desc: '近20日日均成交额(万元)' },
  pe_lyr: { cn: '市盈率(静态)', desc: '股价/上年每股收益' },
  pb: { cn: '市净率', desc: '股价/每股净资产' },
  roe_ttm: { cn: 'ROE(TTM)', desc: '近12月净资产收益率' },
  roe_deducted: { cn: '扣非ROE', desc: '扣非净利润/净资产' },
  cpi_yoy: { cn: 'CPI同比', desc: '居民消费价格指数同比' },
  pmi: { cn: 'PMI', desc: '制造业采购经理指数' },
  m2_yoy: { cn: 'M2同比', desc: '广义货币供应同比' },
  // Alpha factors
  alpha006: { cn: 'Alpha#6 量价相关', desc: '成交量与收益率相关性' },
  alpha012: { cn: 'Alpha#12 量价背离', desc: '量价背离信号' },
  alpha026: { cn: 'Alpha#26 量价共移', desc: '量价同步上升的看空反转' },
  alpha033: { cn: 'Alpha#33 开收盘比', desc: '开盘/收盘比值的反转' },
  alpha044: { cn: 'Alpha#44 低价量相关', desc: '低价与均量相关性' },
  alpha054: { cn: 'Alpha#54 波动反转', desc: '波动率反转因子' },
  alpha085: { cn: 'Alpha#85 量价反相关', desc: '收盘量价反相关' },
  alpha101: { cn: 'Alpha#101 日内幅度', desc: '日内振幅占比' },
}

/** Get a feature's Chinese label, falling back to the raw name. */
export function featureLabel(name: string): string {
  return FEATURE_LABELS[name]?.cn ?? name
}

/** Get a feature's description tooltip. */
export function featureDesc(name: string): string {
  const meta = FEATURE_LABELS[name]
  if (!meta) return name
  return meta.formula ? `${meta.desc} (${meta.formula})` : meta.desc
}
