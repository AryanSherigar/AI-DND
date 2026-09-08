import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw/server";
import { initializeAuthInterceptors } from "@/features/auth/lib/setupAuthInterceptor";

initializeAuthInterceptors();

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
