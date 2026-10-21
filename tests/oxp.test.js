"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync("oxp/CtxKeys.oxp/Config/script.js", "utf8");

function fakeGame() {
	const messages = [];
	const market = {
		food: { price: 42, quantity: 8, legality_export: 0, legality_import: 0 },
		computers: { price: 735, quantity: 3, legality_export: 1, legality_import: 0 }
	};
	const distances = { 7: 0, 8: 6.5, 9: 7.1 };
	const info = [7, 8, 9].map(function (id) {
		return {
			systemID: id,
			name: ["Lave", "Zaonce", "Diso"][id - 7],
			economy: id,
			government: id + 1,
			techlevel: id + 2,
			distanceToSystem: function (other) { return distances[other.systemID]; },
			samplePrice: function (commodity) {
				return (commodity === "food" ? 40 : 730) + id;
			}
		};
	});
	const station = { displayName: "Lave Station", market: market };
	const game = {
		player: {
			credits: 1200.5,
			alertCondition: 1,
			dockingClearanceStatus: "DOCKING_CLEARANCE_STATUS_NONE",
			ship: {
				docked: true,
				dockedStation: station,
				viewDirection: "VIEW_FORWARD",
				withinStationAegis: false,
				cargoSpaceAvailable: 18,
				cargoSpaceCapacity: 35,
				fuel: 7,
				infoSystem: 8,
				targetSystem: 9,
				manifest: {
					list: [{ name: "food", unit: "tonnes", quantity: 2, displayName: "Food" }]
				}
			}
		},
		system: {
			name: "Lave",
			ID: 7,
			info: info[0],
			mainStation: { market: market }
		},
		SystemInfo: {
			filteredSystems: function (_receiver, predicate) {
				return info.filter(predicate);
			}
		},
		log: function (_class, message) { messages.push(JSON.parse(message)); }
	};
	vm.createContext(game);
	vm.runInContext(script, game);
	return { game: game, messages: messages, market: market };
}

test("startup reports market, fuel-range systems, and chart target", function () {
	const fake = fakeGame();
	fake.game.startUpComplete();

	assert.deepEqual(fake.messages.map(message => message.type), [
		"ready", "market", "systems", "chart_target"
	]);
	assert.deepEqual(fake.messages[1], {
		type: "market",
		station: "Lave Station",
		market: fake.market,
		credits: 1200.5,
		cargoSpace: { available: 18, capacity: 35 },
		fuel: 7,
		manifest: [{ name: "food", unit: "tonnes", quantity: 2, displayName: "Food" }]
	});
	assert.deepEqual(JSON.parse(JSON.stringify(fake.messages[2])), {
		type: "systems",
		fuel: 7,
		systems: [
			{
				id: 7,
				name: "Lave",
				distance: 0,
				economy: 7,
				government: 8,
				techLevel: 9,
				samplePrices: { food: 47, computers: 737 }
			},
			{
				id: 8,
				name: "Zaonce",
				distance: 6.5,
				economy: 8,
				government: 9,
				techLevel: 10,
				samplePrices: { food: 48, computers: 738 }
			}
		]
	});
	assert.deepEqual(fake.messages[3], {
		type: "chart_target",
		infoSystem: 8,
		targetSystem: 9
	});
});

test("market screen and cargo events report current Oolite values", function () {
	const fake = fakeGame();
	fake.game.guiScreenChanged("GUI_SCREEN_MARKET", "GUI_SCREEN_STATUS");
	fake.game.playerBoughtCargo("food", 2, 42);
	fake.game.playerSoldCargo("computers", 1, 735);
	fake.game.infoSystemChanged();

	assert.deepEqual(fake.messages.map(message => message.type), [
		"gui", "market", "bought", "sold", "chart_target"
	]);
	assert.equal(fake.messages[1].market.food.price, 42);
	assert.deepEqual(fake.messages[2], {
		type: "bought", commodity: "food", units: 2, price: 42
	});
	assert.deepEqual(fake.messages[3], {
		type: "sold", commodity: "computers", units: 1, price: 735
	});
	assert.deepEqual(fake.messages[4], {
		type: "chart_target", infoSystem: 8, targetSystem: 9
	});
});

test("fuel scooping refreshes the reachable systems", function () {
	const fake = fakeGame();
	fake.game.player.ship.fuel = 3;
	fake.game.shipScoopedFuel();

	assert.equal(fake.messages.length, 1);
	assert.equal(fake.messages[0].type, "systems");
	assert.equal(fake.messages[0].fuel, 3);
	assert.deepEqual(fake.messages[0].systems.map(system => system.id), [7]);
});

test("trade scenario uses the emitted message contract", function () {
	const steps = JSON.parse(fs.readFileSync("scenarios/trade.yaml", "utf8"));
	assert.deepEqual(steps.map(step => step.msg.type), [
		"market", "bought", "sold", "systems", "chart_target"
	]);
	assert.ok("legality_export" in steps[0].msg.market.food);
	assert.ok("samplePrices" in steps[3].msg.systems[0]);
	assert.ok("targetSystem" in steps[4].msg);
});
