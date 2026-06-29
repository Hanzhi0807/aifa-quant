import { z } from "zod";
import { createRouter, protectedQuery } from "../middleware";
import { isDuckDBAvailable, queryDuckDB } from "../queries/duckdb";

interface OrderRow {
  order_id: string;
  trade_date: Date;
  symbol: string;
  side: string;
  quantity: number;
  fill_price: number;
  commission: number;
  stamp_duty: number;
  status: string;
}

function formatDate(d: Date | string | undefined): string {
  if (!d) return "-";
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toISOString().split("T")[0];
}

export const ordersRouter = createRouter({
  list: protectedQuery
    .input(z.object({ profile: z.string().default("balanced") }))
    .query(async ({ input }) => {
      if (!isDuckDBAvailable()) return [];

      const rows = await queryDuckDB<OrderRow>(
        `SELECT order_id, trade_date, symbol, side, quantity, fill_price, commission, stamp_duty, status
         FROM paper_orders
         WHERE profile = ?
         ORDER BY trade_date DESC, order_id DESC`,
        [input.profile],
      );

      return rows.map((r) => ({
        orderId: r.order_id,
        tradeDate: formatDate(r.trade_date),
        symbol: r.symbol,
        side: r.side,
        quantity: Number(r.quantity),
        fillPrice: Number(r.fill_price),
        commission: Number(r.commission),
        stampDuty: Number(r.stamp_duty),
        status: r.status,
      }));
    }),
});
