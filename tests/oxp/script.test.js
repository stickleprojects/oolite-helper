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
		expected: '{"version":"0.3","type":"hello"}',
	},
	{
		name: "entering a station aegis",
		run({ world, player, system }) {
			player.ship.withinStationAegis = true;
			world.shipEnteredStationAegis(system.mainStation);
		},
		expected:
			'{"inside":true,"station":"Test Station","requiresClearance":true,"clearance":"DOCKING_CLEARANCE_STATUS_NONE","type":"aegis"}',
	},
	{
		name: "red alert",
		run({ world }) {
			world.alertConditionChanged(3, 1);
		},
		expected: '{"level":3,"type":"alert"}',
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
			assert.deepEqual(fake.messages(), [scenario.expected]);
			assert.equal(fake.logCalls.length, useDebugConsole ? 0 : 1);
			assert.equal(fake.debugMessages.length, useDebugConsole ? 1 : 0);
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
		fake.player.dockingClearanceStatus = "DOCKING_CLEARANCE_STATUS_EXPIRED";
		timer.tick();
		assert.deepEqual(fake.messages(), [
			'{"inside":true,"station":"Test Station","requiresClearance":true,"clearance":"DOCKING_CLEARANCE_STATUS_GRANTED","type":"aegis"}',
			'{"status":"DOCKING_CLEARANCE_STATUS_TIMING_OUT","event":"changed","type":"clearance"}',
			'{"station":"Test Station","type":"docked"}',
		]);
	});
}
