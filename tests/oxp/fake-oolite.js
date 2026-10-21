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
	// player.ship.docked, player.ship.viewDirection, player.ship.dockedStation,
	// player.ship.infoSystem, and player.ship.targetSystem:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSPlayerShip.m
	// player.credits:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSPlayer.m
	// player.ship.withinStationAegis, fuel, cargo space, and station.displayName:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSShip.m
	// station.requiresDockingClearance and station.market:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSStation.m
	// station.market dictionary fields:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/OOCommodities.h
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/OOCommodityMarket.m
	// system.name, system.ID, system.info, and system.mainStation:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSSystem.m
	// System.infoForSystem() (OOJSSystem.m), SystemInfo.filteredSystems(), SystemInfo.distanceToSystem(),
	// SystemInfo.samplePrice(), SystemInfo.systemID, and system-info data:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSSystemInfo.m
	// ship.manifest.list:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSManifest.m
	// shipScoopedFuel:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Entities/PlayerEntity.m
	// playerBoughtCargo and playerSoldCargo:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Entities/PlayerEntity.m
	// infoSystemChanged:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/Doc/CHANGELOG.TXT
	// entity.isShip, entity.mass, entity.position (OOJSEntity.m),
	// Vector3D.squaredDistanceTo (OOJSVector.m), and
	// entity.scanClass, ship.isCloaked (OOJSShip.m), planet.radius (OOJSPlanet.m),
	// system.planets, system.sun, and
	// system.filteredEntities(this, predicate, relativeTo, range), nearest first:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSSystem.m
	// Docking clearance expiry resets the status to NONE:
	//   https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Entities/StationEntity.m
	const market = {
		food: {
			price: 42,
			quantity: 8,
			quantity_unit: 0,
			legality_export: 0,
			legality_import: 0,
		},
		computers: {
			price: 735,
			quantity: 3,
			quantity_unit: 0,
			legality_export: 1,
			legality_import: 0,
		},
	};
	const vector = (x) => ({
		x,
		squaredDistanceTo(other) {
			return (this.x - other.x) ** 2;
		},
	});
	const station = strictObject("station", {
		isShip: true,
		scanClass: "CLASS_STATION",
		isCloaked: false,
		mass: 455223200, // a Coriolis station: blocks jumps within about 6.7 km
		position: vector(0),
		displayName: "Test Station",
		requiresDockingClearance: true,
		market,
	});
	const systemInfos = [
		{
			systemID: 7,
			name: "Test System",
			economy: 3,
			government: 4,
			techlevel: 5,
			distanceToSystem(other) {
				return other.systemID === 7 ? 0 : other.systemID === 8 ? 6.5 : 7.1;
			},
			samplePrice(commodity) {
				return (commodity === "food" ? 40 : 730) + this.systemID;
			},
		},
		{
			systemID: 8,
			name: "Nearby System",
			economy: 2,
			government: 5,
			techlevel: 6,
			distanceToSystem(other) {
				return other.systemID === 7 ? 6.5 : other.systemID === 8 ? 0 : 6.8;
			},
			samplePrice(commodity) {
				return (commodity === "food" ? 40 : 730) + this.systemID;
			},
		},
		{
			systemID: 9,
			name: "Far System",
			economy: 1,
			government: 6,
			techlevel: 7,
			distanceToSystem(other) {
				return other.systemID === 7 ? 7.1 : other.systemID === 8 ? 6.8 : 0;
			},
			samplePrice(commodity) {
				return (commodity === "food" ? 40 : 730) + this.systemID;
			},
		},
	].map((info) => strictObject("system info", info));
	const player = strictObject("player", {
		alertCondition: 1,
		dockingClearanceStatus: "DOCKING_CLEARANCE_STATUS_NONE",
		credits: 1200.5,
		ship: strictObject("player.ship", {
			docked: false,
			viewDirection: "VIEW_FORWARD",
			withinStationAegis: false,
			dockedStation: station,
			fuel: 7,
			cargoSpaceAvailable: 18,
			cargoSpaceCapacity: 35,
			manifest: strictObject("manifest", {
				list: [
					{ commodity: "food", unit: "t", quantity: 2, displayName: "Food" },
				],
			}),
			infoSystem: 8,
			targetSystem: 9,
			isShip: true,
			mass: 100000,
			position: vector(5000),
		}),
	});
	const system = strictObject("system", {
		mainStation: station,
		name: "Test System",
		ID: 7,
		info: systemInfos[0],
		entities: [station],
		planets: [{ isSun: false, radius: 5000000, position: vector(-1e9) }],
		sun: { isSun: true, radius: 1e8, position: vector(1e12) },
		filteredEntities(_this, predicate, relativeTo, range) {
			return [...this.entities, player.ship]
				.filter((entity) => relativeTo.position.squaredDistanceTo(entity.position) <= range ** 2)
				.filter(predicate)
				.sort(
					(a, b) =>
						relativeTo.position.squaredDistanceTo(a.position) -
						relativeTo.position.squaredDistanceTo(b.position)
				);
		},
	});
	const System = strictObject("System", {
		infoForSystem(galaxy, id) {
			return systemInfos.find((info) => info.systemID === id) || null;
		},
	});
	const SystemInfo = strictObject("SystemInfo", {
		filteredSystems(_this, predicate) {
			return systemInfos.filter(predicate);
		},
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
		System,
		SystemInfo,
		galaxyNumber: 0,
		clock: strictObject("clock", { seconds: 123456 }),
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
