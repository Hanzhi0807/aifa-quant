import { Routes, Route } from "react-router";
import Navigation from "./components/layout/Navigation";
import Home from "./pages/Home";
import Performance from "./pages/Performance";
import Backtest from "./pages/Backtest";
import Models from "./pages/Models";
import Data from "./pages/Data";
import Metrics from "./pages/Metrics";
import Reports from "./pages/Reports";

export default function App() {
  return (
    <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
      <Navigation />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/performance" element={<Performance />} />
        <Route path="/backtest" element={<Backtest />} />
        <Route path="/models" element={<Models />} />
        <Route path="/data" element={<Data />} />
        <Route path="/metrics" element={<Metrics />} />
        <Route path="/reports" element={<Reports />} />
      </Routes>
    </div>
  );
}
