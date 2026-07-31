import { OpenRouter } from "@openrouter/sdk";

const apiKey = process.env.OPENROUTER_API_KEY;
if (!apiKey) throw new Error("OPENROUTER_API_KEY is missing");
const client = new OpenRouter({ apiKey });
const result = await client.datasets.getRankingsDaily();
process.stdout.write(JSON.stringify(result));
