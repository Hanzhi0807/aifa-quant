import { Routes, Route } from "react-router";
import Navigation from "./components/layout/Navigation";
import Home from "./pages/Home";
import Backtest from "./pages/Backtest";
import Models from "./pages/Models";
import Data from "./pages/Data";

export default function App() {
  return (
    <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
      <Navigation />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/backtest" element={<Backtest />} />
        <Route path="/models" element={<Models />} />
        <Route path="/data" element={<Data />} />
      </Routes>
    </div>
  );
}
