import { OpenRouter } from "@openrouter/sdk";

const apiKey = process.env.OPENROUTER_API_KEY;

async function main() {
  if (!apiKey) throw new Error("OPENROUTER_API_KEY is missing");
  const client = new OpenRouter({ apiKey });
  const result = await client.datasets.getRankingsDaily();
  process.stdout.write(JSON.stringify(result));
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  const safeMessage = apiKey ? message.replaceAll(apiKey, "[REDACTED]") : message;
  console.error(`OpenRouter rankings request failed: ${safeMessage}`);
  process.exitCode = 1;
});
