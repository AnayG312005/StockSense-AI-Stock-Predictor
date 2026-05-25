import { useState } from "react";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, RadialBarChart, RadialBar, Legend
} from "recharts";
import {
  TrendingUp, TrendingDown, Bell, Search, BarChart2,
  Activity, Briefcase, Star, Newspaper, Settings,
  ChevronUp, ChevronDown, Zap, Shield, Target,
  AlertTriangle, Home, Brain, Eye, RefreshCcw, Menu
} from "lucide-react";

const priceData = [
  { time: "Jan", actual: 2800, predicted: 2820 },
  { time: "Feb", actual: 2950, predicted: 2970 },
  { time: "Mar", actual: 2870, predicted: 2900 },
  { time: "Apr", actual: 3100, predicted: 3080 },
  { time: "May", actual: 3250, predicted: 3230 },
  { time: "Jun", actual: 3180, predicted: 3200 },
  { time: "Jul", actual: 3400, predicted: 3380 },
  { time: "Aug", actual: 3520, predicted: 3540 },
  { time: "Sep", actual: null, predicted: 3650 },
  { time: "Oct", actual: null, predicted: 3780 },
  { time: "Nov", actual: null, predicted: 3920 },
  { time: "Dec", actual: null, predicted: 4050 },
];

const volumeData = [
  { day: "Mon", volume: 12400 }, { day: "Tue", volume: 18200 },
  { day: "Wed", volume: 9800 }, { day: "Thu", volume: 21000 },
  { day: "Fri", volume: 15600 }, { day: "Sat", volume: 8200 },
  { day: "Sun", volume: 6400 },
];

const rsiData = [
  { t: "1", rsi: 42 }, { t: "2", rsi: 55 }, { t: "3", rsi: 61 },
  { t: "4", rsi: 72 }, { t: "5", rsi: 68 }, { t: "6", rsi: 58 },
  { t: "7", rsi: 49 }, { t: "8", rsi: 53 }, { t: "9", rsi: 65 },
  { t: "10", rsi: 71 }, { t: "11", rsi: 67 }, { t: "12", rsi: 74 },
];

const macdData = [
  { t: "1", macd: 2.1, signal: 1.8, hist: 0.3 },
  { t: "2", macd: 3.4, signal: 2.6, hist: 0.8 },
  { t: "3", macd: 2.8, signal: 2.9, hist: -0.1 },
  { t: "4", macd: 4.2, signal: 3.3, hist: 0.9 },
  { t: "5", macd: 3.9, signal: 3.8, hist: 0.1 },
  { t: "6", macd: 5.1, signal: 4.4, hist: 0.7 },
  { t: "7", macd: 4.7, signal: 4.6, hist: 0.1 },
  { t: "8", macd: 6.0, signal: 5.3, hist: 0.7 },
];

const portfolioData = [
  { name: "Reliance", value: 32, color: "#06b6d4" },
  { name: "TCS", value: 24, color: "#8b5cf6" },
  { name: "Infosys", value: 18, color: "#10b981" },
  { name: "HDFC", value: 14, color: "#f59e0b" },
  { name: "Others", value: 12, color: "#6366f1" },
];

const indices = [
  { name: "NIFTY 50", value: "22,124.15", change: "+1.24%", up: true, spark: [100,102,98,105,108,106,112] },
  { name: "SENSEX", value: "72,891.36", change: "+0.87%", up: true, spark: [100,101,103,101,106,108,110] },
  { name: "NASDAQ", value: "18,244.80", change: "-0.32%", up: false, spark: [112,110,108,105,107,104,103] },
  { name: "DOW JONES", value: "38,892.34", change: "+0.56%", up: true, spark: [100,102,101,104,103,106,108] },
];

const topMovers = [
  { symbol: "RELIANCE", price: "₹2,847.50", change: "+3.2%", up: true },
  { symbol: "TCS", price: "₹3,921.00", change: "+1.8%", up: true },
  { symbol: "HDFC BANK", price: "₹1,624.75", change: "-0.9%", up: false },
  { symbol: "INFY", price: "₹1,482.30", change: "+2.4%", up: true },
  { symbol: "WIPRO", price: "₹478.60", change: "-1.2%", up: false },
];

const alerts = [
  { type: "buy", text: "RELIANCE crossed 200-DMA — Strong BUY signal", time: "2m ago" },
  { type: "alert", text: "TCS RSI overbought (74.2) — Monitor closely", time: "8m ago" },
  { type: "sell", text: "HDFC BANK MACD bearish crossover detected", time: "15m ago" },
  { type: "info", text: "NIFTY approaching resistance at 22,400", time: "32m ago" },
];

const navItems = [
  { icon: Home, label: "Dashboard", active: true },
  { icon: BarChart2, label: "Market Overview", active: false },
  { icon: Brain, label: "AI Predictions", active: false },
  { icon: Activity, label: "Technical Analysis", active: false },
  { icon: Briefcase, label: "Portfolio", active: false },
  { icon: Star, label: "Watchlist", active: false },
  { icon: Newspaper, label: "News & Insights", active: false },
  { icon: Settings, label: "Settings", active: false },
];

function MiniSparkline({ data, up }: { data: number[]; up: boolean }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * 60},${20 - ((v - min) / (max - min + 0.001)) * 18}`).join(" ");
  return (
    <svg width="60" height="20" viewBox="0 0 60 20">
      <polyline points={pts} fill="none" stroke={up ? "#10b981" : "#ef4444"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GlassCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border ${className}`}
      style={{
        background: "rgba(255,255,255,0.04)",
        borderColor: "rgba(255,255,255,0.08)",
        backdropFilter: "blur(12px)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)"
      }}>
      {children}
    </div>
  );
}

function Badge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    buy: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
    sell: "bg-red-500/20 text-red-400 border border-red-500/30",
    hold: "bg-amber-500/20 text-amber-400 border border-amber-500/30",
    alert: "bg-orange-500/20 text-orange-400 border border-orange-500/30",
    info: "bg-blue-500/20 text-blue-400 border border-blue-500/30",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${styles[type] || styles.info}`}>
      {type}
    </span>
  );
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg p-3 text-xs" style={{ background: "rgba(15,15,30,0.95)", border: "1px solid rgba(99,102,241,0.4)" }}>
        <p className="text-slate-400 mb-1">{label}</p>
        {payload.map((p: any, i: number) => (
          <p key={i} style={{ color: p.color }}>{p.name}: <span className="font-bold">{p.value}</span></p>
        ))}
      </div>
    );
  }
  return null;
};

export function Dashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedStock, setSelectedStock] = useState("RELIANCE.NS");

  return (
    <div className="flex h-screen overflow-hidden text-slate-100 text-sm select-none"
      style={{ background: "linear-gradient(135deg, #060818 0%, #0a0f2a 50%, #050d1a 100%)", fontFamily: "'Inter', sans-serif" }}>

      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col border-r py-5"
        style={{ borderColor: "rgba(255,255,255,0.06)", background: "rgba(6,8,24,0.9)" }}>
        {/* Logo */}
        <div className="px-5 mb-8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #6366f1, #06b6d4)" }}>
              <Brain className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-bold text-white text-sm leading-none">StockSense</div>
              <div className="text-[10px] font-medium leading-none mt-0.5" style={{ color: "#06b6d4" }}>AI PLATFORM</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 space-y-0.5">
          {navItems.map(({ icon: Icon, label, active }) => (
            <button key={label}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all ${active ? "text-white" : "text-slate-500 hover:text-slate-300 hover:bg-white/4"}`}
              style={active ? { background: "linear-gradient(90deg, rgba(99,102,241,0.25), rgba(6,182,212,0.1))", borderLeft: "2px solid #6366f1", color: "#e2e8f0" } : {}}>
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="text-xs font-medium">{label}</span>
              {active && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-400" />}
            </button>
          ))}
        </nav>

        {/* Market Status */}
        <div className="mx-3 mt-4 p-3 rounded-xl" style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-emerald-400 text-xs font-semibold">MARKET OPEN</span>
          </div>
          <div className="text-slate-400 text-[10px] mt-1">NSE · BSE · NASDAQ</div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Top Nav */}
        <header className="h-14 flex items-center px-6 gap-4 flex-shrink-0 border-b"
          style={{ borderColor: "rgba(255,255,255,0.06)", background: "rgba(6,8,24,0.8)" }}>
          <div className="flex-1 flex items-center gap-3 max-w-xs">
            <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg"
              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <Search className="w-3.5 h-3.5 text-slate-500" />
              <input className="bg-transparent text-xs text-slate-300 placeholder-slate-600 outline-none w-full"
                placeholder="Search AAPL, TSLA, RELIANCE…"
                value={selectedStock}
                onChange={e => setSelectedStock(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-3 ml-auto">
            <button className="relative p-2 rounded-lg hover:bg-white/5">
              <Bell className="w-4 h-4 text-slate-400" />
              <div className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-indigo-400" />
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white"
                style={{ background: "linear-gradient(135deg, #6366f1, #06b6d4)" }}>A</div>
              <span className="text-xs text-slate-300 font-medium">Analyst</span>
            </div>
            <div className="px-2.5 py-1 rounded-full text-[10px] font-bold"
              style={{ background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.3)", color: "#06b6d4" }}>
              PRO
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-5 space-y-4">

          {/* Page header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-bold text-white">AI Analytics Dashboard</h1>
              <p className="text-xs text-slate-500 mt-0.5">Real-time intelligence · Last updated just now</p>
            </div>
            <div className="flex items-center gap-2">
              {["1D","1W","1M","3M","1Y"].map(t => (
                <button key={t}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${t === "1M" ? "text-white" : "text-slate-500 hover:text-slate-300"}`}
                  style={t === "1M" ? { background: "linear-gradient(90deg, #6366f1, #06b6d4)" } : { background: "rgba(255,255,255,0.04)" }}>
                  {t}
                </button>
              ))}
              <button className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300" style={{ background: "rgba(255,255,255,0.04)" }}>
                <RefreshCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* === MARKET OVERVIEW INDICES === */}
          <div className="grid grid-cols-4 gap-3">
            {indices.map(idx => (
              <GlassCard key={idx.name} className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">{idx.name}</div>
                    <div className="text-base font-bold text-white mt-0.5">{idx.value}</div>
                  </div>
                  <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${idx.up ? "text-emerald-400 bg-emerald-500/10" : "text-red-400 bg-red-500/10"}`}>
                    {idx.up ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {idx.change}
                  </div>
                </div>
                <MiniSparkline data={idx.spark} up={idx.up} />
              </GlassCard>
            ))}
          </div>

          {/* === KPI ROW === */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "AI Confidence", value: "87.4%", sub: "BUY Signal", icon: Brain, color: "#6366f1", glow: "rgba(99,102,241,0.3)" },
              { label: "Model Accuracy", value: "91.2%", sub: "Last 30 days", icon: Target, color: "#06b6d4", glow: "rgba(6,182,212,0.3)" },
              { label: "Portfolio Return", value: "+24.8%", sub: "YTD 2026", icon: TrendingUp, color: "#10b981", glow: "rgba(16,185,129,0.3)" },
              { label: "Risk Score", value: "Medium", sub: "Volatility: 18.3%", icon: Shield, color: "#f59e0b", glow: "rgba(245,158,11,0.3)" },
            ].map(k => (
              <GlassCard key={k.label} className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ background: `${k.glow}`, boxShadow: `0 0 16px ${k.glow}` }}>
                    <k.icon className="w-5 h-5" style={{ color: k.color }} />
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">{k.label}</div>
                    <div className="text-lg font-bold text-white leading-tight">{k.value}</div>
                    <div className="text-[10px] text-slate-500">{k.sub}</div>
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>

          {/* === MAIN CHARTS ROW === */}
          <div className="grid grid-cols-3 gap-3">

            {/* AI Price Prediction Chart */}
            <GlassCard className="col-span-2 p-4">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-xs font-bold text-white flex items-center gap-2">
                    <Brain className="w-4 h-4 text-indigo-400" /> AI Price Prediction — {selectedStock}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">LSTM Deep Learning Model · Historical vs Forecast</div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                    <div className="w-3 h-0.5 rounded bg-cyan-400" /> Actual
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                    <div className="w-3 h-0.5 rounded border-t-2 border-dashed border-indigo-400" /> Predicted
                  </div>
                  <Badge type="buy" />
                </div>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={priceData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="predictGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="actual" stroke="#06b6d4" strokeWidth={2} fill="url(#actualGrad)" name="Actual" dot={false} connectNulls={false} />
                  <Area type="monotone" dataKey="predicted" stroke="#6366f1" strokeWidth={2} strokeDasharray="5 3" fill="url(#predictGrad)" name="Predicted" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
              {/* Confidence bar */}
              <div className="mt-3 flex items-center gap-3">
                <span className="text-[10px] text-slate-500">AI Confidence</span>
                <div className="flex-1 h-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.06)" }}>
                  <div className="h-1.5 rounded-full" style={{ width: "87%", background: "linear-gradient(90deg, #6366f1, #06b6d4)", boxShadow: "0 0 8px rgba(99,102,241,0.6)" }} />
                </div>
                <span className="text-[10px] font-bold text-indigo-400">87%</span>
                <span className="text-[10px] text-slate-500">Target: ₹4,050</span>
                <span className="text-[10px] text-emerald-400 font-semibold">+16.3% upside</span>
              </div>
            </GlassCard>

            {/* Portfolio Donut */}
            <GlassCard className="p-4">
              <div className="text-xs font-bold text-white mb-1 flex items-center gap-2">
                <Briefcase className="w-3.5 h-3.5 text-purple-400" /> Portfolio Allocation
              </div>
              <div className="text-[10px] text-slate-500 mb-3">Total Value: ₹12,84,500</div>
              <ResponsiveContainer width="100%" height={130}>
                <PieChart>
                  <Pie data={portfolioData} cx="50%" cy="50%" innerRadius={40} outerRadius={62}
                    paddingAngle={3} dataKey="value" stroke="none">
                    {portfolioData.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip formatter={(v: any) => `${v}%`} contentStyle={{ background: "rgba(10,15,42,0.95)", border: "1px solid rgba(99,102,241,0.3)", borderRadius: 8, fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-1">
                {portfolioData.map(d => (
                  <div key={d.name} className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: d.color }} />
                    <span className="text-[10px] text-slate-400 flex-1">{d.name}</span>
                    <span className="text-[10px] font-bold text-white">{d.value}%</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>

          {/* === TECHNICAL ANALYSIS ROW === */}
          <div className="grid grid-cols-3 gap-3">

            {/* RSI Chart */}
            <GlassCard className="p-4">
              <div className="text-xs font-bold text-white mb-1 flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-cyan-400" /> RSI Indicator
              </div>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-[10px] text-slate-500">Current RSI:</span>
                <span className="text-sm font-bold text-amber-400">74.2</span>
                <Badge type="hold" />
              </div>
              <ResponsiveContainer width="100%" height={100}>
                <LineChart data={rsiData} margin={{ top: 2, right: 5, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="t" hide />
                  <YAxis domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false} ticks={[30, 50, 70]} />
                  <Tooltip content={<CustomTooltip />} />
                  {/* Overbought/oversold zones */}
                  <Line type="monotone" dataKey="rsi" stroke="#06b6d4" strokeWidth={2} dot={false} name="RSI" />
                </LineChart>
              </ResponsiveContainer>
              <div className="flex justify-between text-[9px] mt-1">
                <span className="text-emerald-400">Oversold &lt;30</span>
                <span className="text-slate-500">Neutral 30-70</span>
                <span className="text-red-400">Overbought &gt;70</span>
              </div>
            </GlassCard>

            {/* MACD */}
            <GlassCard className="p-4">
              <div className="text-xs font-bold text-white mb-1 flex items-center gap-2">
                <BarChart2 className="w-3.5 h-3.5 text-purple-400" /> MACD
              </div>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-[10px] text-slate-500">Signal:</span>
                <span className="text-sm font-bold text-emerald-400">Bullish</span>
                <Badge type="buy" />
              </div>
              <ResponsiveContainer width="100%" height={100}>
                <BarChart data={macdData} margin={{ top: 2, right: 5, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="t" hide />
                  <YAxis tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="hist" name="Histogram" radius={[2, 2, 0, 0]}>
                    {macdData.map((e, i) => <Cell key={i} fill={e.hist >= 0 ? "#10b981" : "#ef4444"} />)}
                  </Bar>
                  <Line type="monotone" dataKey="macd" stroke="#6366f1" strokeWidth={1.5} dot={false} name="MACD" />
                  <Line type="monotone" dataKey="signal" stroke="#f59e0b" strokeWidth={1.5} dot={false} name="Signal" strokeDasharray="4 2" />
                </BarChart>
              </ResponsiveContainer>
            </GlassCard>

            {/* Volume */}
            <GlassCard className="p-4">
              <div className="text-xs font-bold text-white mb-1 flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> Volume Analysis
              </div>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-[10px] text-slate-500">7-day avg:</span>
                <span className="text-sm font-bold text-cyan-400">13.1K</span>
                <span className="text-[10px] text-emerald-400">+8.4%</span>
              </div>
              <ResponsiveContainer width="100%" height={100}>
                <BarChart data={volumeData} margin={{ top: 2, right: 5, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="day" tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="volume" name="Volume" radius={[2, 2, 0, 0]}>
                    {volumeData.map((e, i) => (
                      <Cell key={i} fill={`rgba(6,182,212,${0.4 + (e.volume / 25000) * 0.6})`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </GlassCard>
          </div>

          {/* === BOTTOM ROW === */}
          <div className="grid grid-cols-3 gap-3">

            {/* Top Movers */}
            <GlassCard className="p-4">
              <div className="text-xs font-bold text-white mb-3 flex items-center gap-2">
                <Zap className="w-3.5 h-3.5 text-amber-400" /> Top Movers Today
              </div>
              <div className="space-y-2">
                {topMovers.map(s => (
                  <div key={s.symbol} className="flex items-center justify-between p-2 rounded-lg"
                    style={{ background: "rgba(255,255,255,0.03)" }}>
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg flex items-center justify-center text-[9px] font-bold text-white"
                        style={{ background: s.up ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)" }}>
                        {s.symbol.slice(0, 2)}
                      </div>
                      <span className="text-[10px] font-semibold text-slate-300">{s.symbol}</span>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] font-bold text-white">{s.price}</div>
                      <div className={`text-[10px] font-bold ${s.up ? "text-emerald-400" : "text-red-400"}`}>{s.change}</div>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* AI Recommendations */}
            <GlassCard className="p-4">
              <div className="text-xs font-bold text-white mb-3 flex items-center gap-2">
                <Brain className="w-3.5 h-3.5 text-indigo-400" /> AI Recommendations
              </div>
              <div className="space-y-2">
                {[
                  { stock: "RELIANCE.NS", rec: "buy", price: "₹2,847", target: "₹3,200", conf: 87 },
                  { stock: "TCS.NS", rec: "hold", price: "₹3,921", target: "₹4,100", conf: 72 },
                  { stock: "HDFC.NS", rec: "sell", price: "₹1,624", target: "₹1,450", conf: 68 },
                ].map(r => (
                  <div key={r.stock} className="p-2.5 rounded-lg space-y-1.5"
                    style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-200">{r.stock}</span>
                      <Badge type={r.rec} />
                    </div>
                    <div className="flex items-center gap-3 text-[9px] text-slate-500">
                      <span>CMP: <span className="text-white">{r.price}</span></span>
                      <span>Target: <span className="text-emerald-400">{r.target}</span></span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1 rounded-full" style={{ background: "rgba(255,255,255,0.06)" }}>
                        <div className="h-1 rounded-full"
                          style={{ width: `${r.conf}%`, background: r.rec === "buy" ? "linear-gradient(90deg,#10b981,#06b6d4)" : r.rec === "sell" ? "linear-gradient(90deg,#ef4444,#f59e0b)" : "linear-gradient(90deg,#f59e0b,#eab308)" }} />
                      </div>
                      <span className="text-[9px] font-bold text-slate-400">{r.conf}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* Smart Alerts */}
            <GlassCard className="p-4">
              <div className="text-xs font-bold text-white mb-3 flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-orange-400" /> Smart Alerts
                <div className="ml-auto w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center"
                  style={{ background: "rgba(239,68,68,0.2)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.3)" }}>
                  {alerts.length}
                </div>
              </div>
              <div className="space-y-2">
                {alerts.map((a, i) => (
                  <div key={i} className="flex gap-2 p-2 rounded-lg"
                    style={{ background: "rgba(255,255,255,0.025)" }}>
                    <Badge type={a.type} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] text-slate-300 leading-snug">{a.text}</div>
                      <div className="text-[9px] text-slate-600 mt-0.5">{a.time}</div>
                    </div>
                  </div>
                ))}
              </div>
              {/* Sentiment Gauge */}
              <div className="mt-3 p-2.5 rounded-lg" style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)" }}>
                <div className="text-[10px] text-slate-400 mb-2">Market Sentiment</div>
                <div className="flex items-center gap-2">
                  <span className="text-[9px] text-red-400">Bearish</span>
                  <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                    <div className="h-2 rounded-full" style={{ width: "68%", background: "linear-gradient(90deg, #ef4444 0%, #f59e0b 50%, #10b981 100%)" }} />
                  </div>
                  <span className="text-[9px] text-emerald-400">Bullish</span>
                </div>
                <div className="text-center text-[10px] font-bold text-indigo-400 mt-1">68% Bullish</div>
              </div>
            </GlassCard>
          </div>

          {/* Branding footer */}
          <div className="text-center py-2 text-[10px] text-slate-700">
            StockSense AI · LSTM Deep Learning · Real-time Analytics · © 2026
          </div>
        </main>
      </div>
    </div>
  );
}
