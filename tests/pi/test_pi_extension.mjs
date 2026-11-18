import test from "node:test";
import assert from "node:assert/strict";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const extUrl = pathToFileURL(resolve(import.meta.dirname, "../../.pi/extensions/superlite.ts")).href;
const { default: ext } = await import(extUrl);

function load() {
	const handlers = {};
	ext({
		on(event, handler) {
			(handlers[event] ??= []).push(handler);
		},
	});
	return handlers;
}

const user = (text) => ({ role: "user", content: [{ type: "text", text }] });
const MARK = "superlite:using-superlite bootstrap for pi";

test("no resources_discover handler", () => {
	assert.equal(load().resources_discover, undefined);
});

test("bootstrap on first prompt", async () => {
	const h = load();
	const r = await h.context[0]({ messages: [user("one")] });
	assert.equal(r.messages.length, 2);
	assert.ok(r.messages[0].content[0].text.startsWith(MARK));
});

test("bootstrap survives agent_end", async () => {
	const h = load();
	const first = await h.context[0]({ messages: [user("one")] });
	for (const fn of h.agent_end ?? []) await fn({});
	const r = await h.context[0]({
		messages: [user("one"), { role: "assistant", content: [{ type: "text", text: "ok" }] }, user("two")],
	});
	assert.equal(r.messages.length, 4);
	assert.equal(r.messages[0].content[0].text, first.messages[0].content[0].text);
});

test("no duplicate bootstrap", async () => {
	const h = load();
	const first = await h.context[0]({ messages: [user("one")] });
	const r = await h.context[0]({ messages: first.messages });
	assert.equal(r, undefined);
});

test("bootstrap after compaction summary", async () => {
	const h = load();
	const r = await h.context[0]({ messages: [{ role: "compactionSummary" }, user("one")] });
	assert.equal(r.messages[0].role, "compactionSummary");
	assert.ok(r.messages[1].content[0].text.startsWith(MARK));
});
