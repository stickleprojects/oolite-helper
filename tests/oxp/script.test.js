"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { createFakeOolite } = require("./fake-oolite.js");

const scenarios = [
	{
		name: "startup",
		run({ world }) {
			world.startUp();
		},
		expected: ['{"version":"0.5","type":"hello"}'],
	},
	{
		name: "startup complete while docked",
		run({ world, player }) {
			player.ship.docked = true;
			player.ship.viewDirection = "VIEW_AFT";
			player.alertCondition = 0;
			world.startUpComplete();
		},
		expected: [
			'{"docked":true,"view":"VIEW_AFT","alert":0,"type":"ready"}',
			'{"galaxy":0,"systemID":7,"systemName":"Test System","gameClock":123456,"station":"Test Station","market":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"credits":1200.5,"cargoSpace":{"available":18,"capacity":35},"fuel":7,"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"market"}',
			'{"galaxy":0,"fuel":7,"systems":[{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}}],"type":"systems"}',
			'{"infoSystem":8,"targetSystem":9,"currentSystem":7,"system":{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}},"originMarket":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"chart_target"}',
			'{"items":[{"key":"EQ_ECM","name":"E.C.M. System","count":1,"description":"Electronic Counter Measures.","status":"EQUIPMENT_OK","provides":[]},{"key":"EQ_HEAT_SHIELD","name":"Heat Shield","count":2,"description":"Two of them.","status":"EQUIPMENT_OK","provides":[]}],"missiles":{"capacity":4,"loaded":[{"key":"EQ_MISSILE","name":"Missile","count":2}]},"type":"equipment"}',
		],
	},
	{
		name: "startup complete in flight",
		run({ world, player }) {
			player.ship.viewDirection = "VIEW_PORT";
			player.alertCondition = 2;
			world.startUpComplete();
		},
		expected: [
			'{"docked":false,"view":"VIEW_PORT","alert":2,"type":"ready"}',
			'{"inside":false,"station":null,"requiresClearance":null,"clearance":"DOCKING_CLEARANCE_STATUS_NONE","type":"aegis"}',
			'{"galaxy":0,"fuel":7,"systems":[{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}}],"type":"systems"}',
			'{"infoSystem":8,"targetSystem":9,"currentSystem":7,"system":{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}},"originMarket":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"chart_target"}',
			'{"items":[{"key":"EQ_ECM","name":"E.C.M. System","count":1,"description":"Electronic Counter Measures.","status":"EQUIPMENT_OK","provides":[]},{"key":"EQ_HEAT_SHIELD","name":"Heat Shield","count":2,"description":"Two of them.","status":"EQUIPMENT_OK","provides":[]}],"missiles":{"capacity":4,"loaded":[{"key":"EQ_MISSILE","name":"Missile","count":2}]},"type":"equipment"}',
		],
	},
	{
		name: "GUI screen change",
		run({ world }) {
			world.guiScreenChanged("GUI_SCREEN_STATUS", "GUI_SCREEN_MAIN");
		},
		expected: ['{"to":"GUI_SCREEN_STATUS","from":"GUI_SCREEN_MAIN","type":"gui"}'],
	},
	{
		name: "entering the market screen while docked",
		run({ world, player }) {
			player.ship.docked = true;
			world.guiScreenChanged("GUI_SCREEN_MARKET", "GUI_SCREEN_STATUS");
		},
		expected: [
			'{"to":"GUI_SCREEN_MARKET","from":"GUI_SCREEN_STATUS","type":"gui"}',
			'{"galaxy":0,"systemID":7,"systemName":"Test System","gameClock":123456,"station":"Test Station","market":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"credits":1200.5,"cargoSpace":{"available":18,"capacity":35},"fuel":7,"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"market"}',
		],
	},
	{
		name: "view direction change",
		run({ world }) {
			world.viewDirectionChanged("VIEW_AFT", "VIEW_FORWARD");
		},
		expected: ['{"to":"VIEW_AFT","from":"VIEW_FORWARD","type":"view"}'],
	},
	{
		name: "docking at a station",
		run({ world, system }) {
			world.shipDockedWithStation(system.mainStation);
		},
		expected: [
			'{"station":"Test Station","type":"docked"}',
			'{"galaxy":0,"systemID":7,"systemName":"Test System","gameClock":123456,"station":"Test Station","market":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"credits":1200.5,"cargoSpace":{"available":18,"capacity":35},"fuel":7,"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"market"}',
			'{"galaxy":0,"fuel":7,"systems":[{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}}],"type":"systems"}',
		],
	},
	{
		name: "preparing to launch",
		run({ world, system }) {
			world.shipWillLaunchFromStation(system.mainStation);
		},
		expected: ['{"station":"Test Station","type":"launching"}'],
	},
	{
		name: "launching into a station aegis",
		run({ world, player, system }) {
			player.ship.withinStationAegis = true;
			player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_GRANTED";
			world.shipLaunchedFromStation(system.mainStation);
		},
		expected: [
			'{"inside":true,"station":"Test Station","requiresClearance":true,"clearance":"DOCKING_CLEARANCE_STATUS_GRANTED","type":"aegis"}',
		],
	},
	{
		name: "entering a station aegis",
		run({ world, player, system }) {
			// As in the game (ShipEntity checkForAegis): the property still has
			// the old value while the event runs.
			player.ship.withinStationAegis = false;
			world.shipEnteredStationAegis(system.mainStation);
		},
		expected: [
			'{"inside":true,"station":"Test Station","requiresClearance":true,"clearance":"DOCKING_CLEARANCE_STATUS_NONE","type":"aegis"}',
		],
	},
	{
		name: "exiting a station aegis",
		run({ world, player, system }) {
			world.shipEnteredStationAegis(system.mainStation);
			player.ship.withinStationAegis = true; // still true while the exit event runs
			world.shipExitedStationAegis(system.mainStation);
		},
		expected: [
			'{"inside":true,"station":"Test Station","requiresClearance":true,"clearance":"DOCKING_CLEARANCE_STATUS_NONE","type":"aegis"}',
			'{"inside":false,"station":null,"requiresClearance":null,"clearance":"DOCKING_CLEARANCE_STATUS_NONE","type":"aegis"}',
		],
	},
	{
		name: "requesting docking clearance",
		run({ world, player }) {
			player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_REQUESTED";
			world.playerRequestedDockingClearance("Clearance requested");
		},
		expected: ['{"status":"DOCKING_CLEARANCE_STATUS_REQUESTED","event":"requested","type":"clearance"}'],
	},
	{
		name: "granting docking clearance",
		run({ world, player }) {
			player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_GRANTED";
			world.playerDockingClearanceGranted();
		},
		expected: ['{"status":"DOCKING_CLEARANCE_STATUS_GRANTED","event":"granted","type":"clearance"}'],
	},
	{
		name: "expiring docking clearance",
		run({ world, player }) {
			player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_NONE";
			world.playerDockingClearanceExpired();
		},
		expected: ['{"status":"DOCKING_CLEARANCE_STATUS_NONE","event":"expired","type":"clearance"}'],
	},
	{
		name: "cancelling docking clearance",
		run({ world, player }) {
			player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_NONE";
			world.playerDockingClearanceCancelled();
		},
		expected: ['{"status":"DOCKING_CLEARANCE_STATUS_NONE","event":"cancelled","type":"clearance"}'],
	},
	{
		name: "refusing docking",
		run({ world, player, system }) {
			player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_NONE";
			world.playerDockingRefused(system.mainStation);
		},
		expected: ['{"status":"DOCKING_CLEARANCE_STATUS_NONE","event":"refused","type":"clearance"}'],
	},
	{
		name: "starting autopilot",
		run({ world, system }) {
			world.playerStartedAutoPilot(system.mainStation);
		},
		expected: ['{"on":true,"type":"autopilot"}'],
	},
	{
		name: "cancelling autopilot",
		run({ world }) {
			world.playerCancelledAutoPilot();
		},
		expected: ['{"on":false,"type":"autopilot"}'],
	},
	{
		name: "red alert",
		run({ world }) {
			world.alertConditionChanged(3, 1);
		},
		expected: ['{"level":3,"type":"alert"}'],
	},
	{
		name: "standard jump countdown",
		run({ world }) {
			world.playerStartedJumpCountdown("standard", 15);
		},
		expected: ['{"kind":"standard","seconds":15,"type":"countdown"}'],
	},
	{
		name: "galactic jump countdown",
		run({ world }) {
			world.playerStartedJumpCountdown("galactic", 30);
		},
		expected: ['{"kind":"galactic","seconds":30,"type":"countdown"}'],
	},
	{
		name: "cancelled jump countdown",
		run({ world }) {
			world.playerCancelledJumpCountdown();
		},
		expected: ['{"reason":"cancelled","type":"countdown_end"}'],
	},
	{
		name: "failed jump countdown",
		run({ world }) {
			world.playerJumpFailed("misjump");
		},
		expected: ['{"reason":"misjump","type":"countdown_end"}'],
	},
	{
		name: "entering witchspace",
		run({ world }) {
			world.shipWillEnterWitchspace("hyperspace");
		},
		expected: ['{"reason":"jumped","cause":"hyperspace","type":"countdown_end"}'],
	},
	{
		name: "exiting witchspace",
		run({ world, player }) {
			player.alertCondition = 2;
			player.ship.withinStationAegis = true;
			world.shipExitedWitchspace();
		},
		expected: [
			'{"system":"Test System","alert":2,"type":"arrived"}',
			'{"inside":true,"station":"Test Station","requiresClearance":true,"clearance":"DOCKING_CLEARANCE_STATUS_NONE","type":"aegis"}',
			'{"galaxy":0,"fuel":7,"systems":[{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}}],"type":"systems"}',
			'{"infoSystem":8,"targetSystem":9,"currentSystem":7,"system":{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}},"originMarket":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"chart_target"}',
		],
	},
	{
		name: "buying cargo",
		run({ world }) {
			world.playerBoughtCargo("food", 2, 42);
		},
		expected: ['{"galaxy":0,"systemID":7,"systemName":"Test System","gameClock":123456,"commodity":"food","units":2,"price":42,"type":"bought"}', '{"galaxy":0,"systemID":7,"systemName":"Test System","gameClock":123456,"station":"Test Station","market":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"credits":1200.5,"cargoSpace":{"available":18,"capacity":35},"fuel":7,"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"market"}'],
	},
	{
		name: "selling cargo",
		run({ world }) {
			world.playerSoldCargo("computers", 1, 735);
		},
		expected: ['{"galaxy":0,"systemID":7,"systemName":"Test System","gameClock":123456,"commodity":"computers","units":1,"price":735,"type":"sold"}', '{"galaxy":0,"systemID":7,"systemName":"Test System","gameClock":123456,"station":"Test Station","market":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"credits":1200.5,"cargoSpace":{"available":18,"capacity":35},"fuel":7,"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"market"}'],
	},
	{
		name: "buying fuel sends the systems now in range and the market",
		run({ world }) {
			world.playerBoughtEquipment("EQ_FUEL", 12);
			world.playerBoughtEquipment("EQ_ECM", 600); // other equipment: the list again
		},
		expected: [
			'{"galaxy":0,"fuel":7,"systems":[{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}}],"type":"systems"}',
			'{"galaxy":0,"systemID":7,"systemName":"Test System","gameClock":123456,"station":"Test Station","market":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"credits":1200.5,"cargoSpace":{"available":18,"capacity":35},"fuel":7,"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"market"}',
			'{"items":[{"key":"EQ_ECM","name":"E.C.M. System","count":1,"description":"Electronic Counter Measures.","status":"EQUIPMENT_OK","provides":[]},{"key":"EQ_HEAT_SHIELD","name":"Heat Shield","count":2,"description":"Two of them.","status":"EQUIPMENT_OK","provides":[]}],"missiles":{"capacity":4,"loaded":[{"key":"EQ_MISSILE","name":"Missile","count":2}]},"type":"equipment"}',
		],
	},
	{
		name: "equipment fitted, damaged, repaired and removed",
		run({ world, player, equipmentInfo, damaged }) {
			player.ship.equipment.length = 0;
			player.ship.equipment.push(equipmentInfo("EQ_FUEL_INJECTION", "Fuel Injectors", "Burn fuel."));
			world.equipmentAdded("EQ_FUEL_INJECTION");
			damaged.add("EQ_FUEL_INJECTION");
			world.equipmentDamaged("EQ_FUEL_INJECTION");
			damaged.clear();
			world.equipmentRepaired("EQ_FUEL_INJECTION");
			player.ship.equipment.length = 0;
			world.equipmentRemoved("EQ_FUEL_INJECTION");
		},
		expected: [
			'{"items":[{"key":"EQ_FUEL_INJECTION","name":"Fuel Injectors","count":1,"description":"Burn fuel.","status":"EQUIPMENT_OK","provides":[]}],"missiles":{"capacity":4,"loaded":[{"key":"EQ_MISSILE","name":"Missile","count":2}]},"type":"equipment"}',
			'{"items":[{"key":"EQ_FUEL_INJECTION","name":"Fuel Injectors","count":1,"description":"Burn fuel.","status":"EQUIPMENT_DAMAGED","provides":[]}],"missiles":{"capacity":4,"loaded":[{"key":"EQ_MISSILE","name":"Missile","count":2}]},"type":"equipment"}',
			'{"items":[{"key":"EQ_FUEL_INJECTION","name":"Fuel Injectors","count":1,"description":"Burn fuel.","status":"EQUIPMENT_OK","provides":[]}],"missiles":{"capacity":4,"loaded":[{"key":"EQ_MISSILE","name":"Missile","count":2}]},"type":"equipment"}',
			'{"items":[],"missiles":{"capacity":4,"loaded":[{"key":"EQ_MISSILE","name":"Missile","count":2}]},"type":"equipment"}',
		],
	},
	{
		name: "a missile fired leaves one pylon fewer",
		run({ world, player }) {
			player.ship.missiles.pop();
			world.shipFiredMissile({}, null);
		},
		expected: [
			'{"items":[{"key":"EQ_ECM","name":"E.C.M. System","count":1,"description":"Electronic Counter Measures.","status":"EQUIPMENT_OK","provides":[]},{"key":"EQ_HEAT_SHIELD","name":"Heat Shield","count":2,"description":"Two of them.","status":"EQUIPMENT_OK","provides":[]}],"missiles":{"capacity":4,"loaded":[{"key":"EQ_MISSILE","name":"Missile","count":1}]},"type":"equipment"}',
		],
	},
	{
		name: "chart info system changed",
		run({ world, player }) {
			player.ship.infoSystem = 8;
			player.ship.targetSystem = 9;
			world.infoSystemChanged();
		},
		expected: ['{"infoSystem":8,"targetSystem":9,"currentSystem":7,"system":{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}},"originMarket":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"chart_target"}'],
	},
	{
		name: "dying names the killer and damage type",
		run({ world }) {
			world.shipDied({ displayName: "Krait" }, "energy damage");
		},
		expected: ['{"cause":"energy damage","by":"Krait","type":"died"}'],
	},
	{
		name: "dying with no killer",
		run({ world }) {
			world.shipDied(null, "scrape damage");
		},
		expected: ['{"cause":"scrape damage","by":null,"type":"died"}'],
	},
	{
		name: "fuel scooping emits a systems update",
		run({ world }) {
			world.shipScoopedFuel();
		},
		expected: [
			'{"galaxy":0,"fuel":7,"systems":[{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}}],"type":"systems"}',
		],
	},
];

test("unknown Oolite properties fail loudly", () => {
	const fake = createFakeOolite();
	assert.throws(
		() => fake.player.ship.viewDireciton,
		/Unexpected player\.ship property: viewDireciton/
	);
});

for (const useDebugConsole of [false, true]) {
	const transport = useDebugConsole ? "debugConsole" : "log";
	for (const scenario of scenarios) {
		test(`${scenario.name} emits exact JSON through ${transport}`, () => {
			const fake = createFakeOolite({ debugConsole: useDebugConsole });
			scenario.run(fake);
			assert.deepEqual(fake.messages(), scenario.expected);
			assert.equal(fake.logCalls.length, useDebugConsole ? 0 : scenario.expected.length);
			assert.equal(fake.debugMessages.length, useDebugConsole ? scenario.expected.length : 0);
		});
	}

	test(`clearance changes are ticked and stop on docking through ${transport}`, () => {
		const fake = createFakeOolite({ debugConsole: useDebugConsole });
		fake.player.ship.withinStationAegis = true;
		fake.player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_GRANTED";
		fake.world.shipEnteredStationAegis(fake.system.mainStation);

		assert.equal(fake.timers.length, 1);
		const [timer] = fake.timers;
		assert.equal(timer.interval, 1);
		fake.player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_TIMING_OUT";
		timer.tick();
		fake.world.shipDockedWithStation(fake.system.mainStation);

		assert.equal(timer.stopped, true);
		fake.player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_NONE";
		timer.tick();
		assert.deepEqual(fake.messages(), [
			'{"inside":true,"station":"Test Station","requiresClearance":true,"clearance":"DOCKING_CLEARANCE_STATUS_GRANTED","type":"aegis"}',
			'{"status":"DOCKING_CLEARANCE_STATUS_TIMING_OUT","event":"changed","type":"clearance"}',
			'{"station":"Test Station","type":"docked"}',
			'{"galaxy":0,"systemID":7,"systemName":"Test System","gameClock":123456,"station":"Test Station","market":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0},"computers":{"price":735,"quantity":3,"quantity_unit":0,"legality_export":1,"legality_import":0}},"credits":1200.5,"cargoSpace":{"available":18,"capacity":35},"fuel":7,"manifest":[{"commodity":"food","unit":"t","quantity":2,"displayName":"Food"}],"type":"market"}',
			'{"galaxy":0,"fuel":7,"systems":[{"id":8,"name":"Nearby System","distance":6.5,"economy":2,"government":5,"techLevel":6,"samplePrices":{"food":48,"computers":738}}],"type":"systems"}',
		]);
	});

	test(`jump blockers and mass locks are reported on change through ${transport}`, () => {
		const fake = createFakeOolite({ debugConsole: useDebugConsole });
		fake.world.shipLaunchedFromStation(fake.system.mainStation);
		const [timer] = fake.timers.filter((t) => t.callback === fake.world._checkFlight);
		fake.logCalls.length = fake.debugMessages.length = 0;
		const ship = fake.player.ship;
		timer.tick(); // 5 km from the station: blocked and locked
		timer.tick(); // unchanged: nothing new
		ship.position = { ...ship.position, x: 8000 };
		timer.tick(); // past 6.7 km: the jump is clear, the drive still locked
		ship.position = { ...ship.position, x: 30000 };
		timer.tick(); // off the scanner: clear
		ship.position = { ...ship.position, x: -1e9 + 5020000 };
		timer.tick(); // 20 km above the planet: locked by it
		fake.world.shipDockedWithStation(fake.system.mainStation);
		assert.equal(timer.stopped, true);
		assert.deepEqual(fake.messages().slice(0, 6), [
			'{"by":"Test Station","clearAt":6747,"type":"jump_blocker"}',
			'{"by":"Test Station","type":"mass_lock"}',
			'{"by":null,"clearAt":null,"type":"jump_blocker"}',
			'{"by":null,"type":"mass_lock"}',
			'{"by":"planet","type":"mass_lock"}',
			'{"station":"Test Station","type":"docked"}',
		]);
	});

	test(`clearance checks stop when the ship dies through ${transport}`, () => {
		const fake = createFakeOolite({ debugConsole: useDebugConsole });
		fake.player.ship.withinStationAegis = true;
		fake.world.shipEnteredStationAegis(fake.system.mainStation);
		const [timer] = fake.timers;
		fake.world.shipDied(null, "energy damage");
		assert.equal(timer.stopped, true);
	});

	test(`repeated fuel scoops with unchanged range do not emit through ${transport}`, () => {
		const fake = createFakeOolite({ debugConsole: useDebugConsole });
		fake.world.startUpComplete();
		const initialMessages = fake.messages().slice();
		fake.player.ship.fuel = 6;
		fake.world.shipScoopedFuel();
		assert.equal(fake.messages().length, initialMessages.length + 1);
		assert.equal(JSON.parse(fake.messages().at(-1)).systems.length, 0);
		const reducedRangeMessages = fake.messages().slice();
		fake.world.shipScoopedFuel();
		fake.world.shipScoopedFuel();
		assert.deepEqual(fake.messages(), reducedRangeMessages);
		fake.player.ship.fuel = 6.5;
		fake.world.shipScoopedFuel();
		assert.equal(JSON.parse(fake.messages().at(-1)).systems[0].id, 8);
		const expandedRangeMessages = fake.messages().slice();
		fake.world.shipScoopedFuel();
		assert.deepEqual(fake.messages(), expandedRangeMessages);
	});
}
