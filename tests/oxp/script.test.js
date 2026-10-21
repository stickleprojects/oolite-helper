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
		expected: ['{"version":"0.3","type":"hello"}'],
	},
	{
		name: "startup complete while docked",
		run({ world, player }) {
			player.ship.docked = true;
			player.ship.viewDirection = "VIEW_AFT";
			player.alertCondition = 0;
			world.startUpComplete();
		},
		expected: ['{"docked":true,"view":"VIEW_AFT","alert":0,"type":"ready"}'],
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
		expected: ['{"station":"Test Station","type":"docked"}'],
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
			player.ship.withinStationAegis = true;
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
			player.ship.withinStationAegis = false;
			world.shipExitedStationAegis(system.mainStation);
		},
		expected: [
			'{"inside":false,"station":"Test Station","requiresClearance":true,"clearance":"DOCKING_CLEARANCE_STATUS_NONE","type":"aegis"}',
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
		]);
	});
}
