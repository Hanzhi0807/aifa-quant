import { initTRPC, TRPCError } from "@trpc/server";
import superjson from "superjson";
import type { TrpcContext } from "./context";
import { env } from "./lib/env";

const t = initTRPC.context<TrpcContext>().create({
  transformer: superjson,
});

const authMiddleware = t.middleware(async ({ ctx, next }) => {
  const authHeader = ctx.req.headers.get("authorization");
  if (
    !env.appSecret ||
    !authHeader?.startsWith("Bearer ") ||
    authHeader.slice(7) !== env.appSecret
  ) {
    throw new TRPCError({ code: "UNAUTHORIZED" });
  }
  return next();
});

export const createRouter = t.router;
export const publicQuery = t.procedure;
export const protectedQuery = t.procedure.use(authMiddleware);
