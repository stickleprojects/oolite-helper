"use strict";

const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const scriptPath = path.resolve(
	__dirname,
	"../../oxp/CtxKeys.oxp/Config/script.js"
);

function strictObject(name, properties) {
	return new Proxy(properties, {
		get(target, property, receiver) {
			if (typeof property === "string" && !Object.hasOwn(target, property)) {
				throw new Error(`Unexpected ${name} property: ${property}`);
			}
			return Reflect.get(target, property, receiver);
		},
		set(target, property, value, receiver) {
			if (typeof property === "string" && !Object.hasOwn(target, property)) {
				throw new Error(`Unexpected ${name} property: ${property}`);
			}
			return Reflect.set(target, property, value, receiver);
		},
	});
}

function createFakeOolite({ debugConsole = false } = {}) {
	const logCalls = [];
	const debugMessages = [];
	const timers = [];

	// Oolite 1.92.1 JavaScript bindings:
	// player.alertCondition and player.dockingClearanceStatus:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSPlayer.m
	// player.ship.docked and player.ship.viewDirection:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSPlayerShip.m
	// player.ship.withinStationAegis and station.displayName:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSShip.m
	// station.requiresDockingClearance:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSStation.m
	const station = strictObject("station", {
		displayName: "Test Station",
		requiresDockingClearance: true,
	});
	const player = strictObject("player", {
		alertCondition: 1,
		dockingClearanceStatus: "DOCKING_CLEARANCE_STATUS_NONE",
		ship: strictObject("player.ship", {
			docked: false,
			viewDirection: "VIEW_FORWARD",
			withinStationAegis: false,
		}),
	});
	const system = strictObject("system", {
		mainStation: station,
		name: "Test System",
	});

	class ManualTimer {
		constructor(target, callback, interval, repeats) {
			this.target = target;
			this.callback = callback;
			this.interval = interval;
			this.repeats = repeats;
			this.stopped = false;
			timers.push(this);
		}

		tick() {
			if (!this.stopped) {
				this.callback.call(this.target);
			}
		}

		stop() {
			this.stopped = true;
		}
	}

	const world = {
		player,
		system,
		Timer: ManualTimer,
		log: (...args) => logCalls.push(args),
	};
	if (debugConsole) {
		world.debugConsole = strictObject("debugConsole", {
			consoleMessage: (message) => debugMessages.push(message),
		});
	}

	vm.runInNewContext(fs.readFileSync(scriptPath, "utf8"), world, {
		filename: scriptPath,
	});

	return {
		world,
		player,
		system,
		logCalls,
		debugMessages,
		timers,
		messages() {
			if (debugConsole) {
				return debugMessages;
			}
			return logCalls.map(([category, message]) => {
				if (category !== "ctxkeys") {
					throw new Error(`Unexpected log category: ${category}`);
				}
				return message;
			});
		},
	};
}

module.exports = { createFakeOolite };
