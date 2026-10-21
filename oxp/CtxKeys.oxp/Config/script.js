"use strict";

this.name = "ctxkeys";
this.author = "Kieron";
this.version = "0.3";
this.description = "Logs game context changes for the external Oolite key helper.";

// All messages leave the game through here, as JSON with a "type" field.
// Debug builds with a console connected get them over TCP; otherwise they go
// to Latest.log as "[ctxkeys]: {json}".
this._emit = function (type, data) {
	data = data || {};
	data.type = type;
	var json = JSON.stringify(data);
	if (typeof debugConsole !== "undefined" && debugConsole) {
		debugConsole.consoleMessage(json);
	} else {
		log("ctxkeys", json);
	}
};

// Station aegis state, with what the helper needs to know about docking there.
this._emitAegis = function (station) {
	var inside = player.ship.withinStationAegis;
	if (!station && inside) {
		station = system.mainStation;
	}
	this._watchClearance(inside);
	this._emit("aegis", {
		inside: inside,
		station: station ? station.displayName : null,
		requiresClearance: station ? station.requiresDockingClearance : null,
		clearance: player.dockingClearanceStatus
	});
};

this._emitClearance = function (event) {
	this._lastClearance = player.dockingClearanceStatus;
	this._emit("clearance", { status: this._lastClearance, event: event });
};

this._marketLocation = function () {
	return {
		galaxy: galaxyNumber,
		systemID: system.ID,
		systemName: system.name,
		gameClock: clock.seconds
	};
};

this._emitMarket = function (station) {
	station = station || player.ship.dockedStation;
	if (!station) return;
	var data = this._marketLocation();
	data.station = station.displayName;
	data.market = station.market;
	data.credits = player.credits;
	data.cargoSpace = {
		available: player.ship.cargoSpaceAvailable,
		capacity: player.ship.cargoSpaceCapacity
	};
	data.fuel = player.ship.fuel;
	data.manifest = player.ship.manifest.list;
	this._emit("market", data);
};

this._emitSystems = function (onlyIfChanged) {
	var fuel = player.ship.fuel;
	var station = system.mainStation;
	var market = station ? station.market : {};
	var commodities = Object.keys(market);
	var origin = system.info;
	var nearby = SystemInfo.filteredSystems(this, function (info) {
		return info.systemID !== system.ID && origin.distanceToSystem(info) <= fuel;
	});
	var ids = nearby.map(function (info) { return info.systemID; }).sort(function (a, b) {
		return a - b;
	});
	if (onlyIfChanged && this._lastReachableSystems &&
			ids.length === this._lastReachableSystems.length &&
			ids.every(function (id, index) { return id === this._lastReachableSystems[index]; }, this)) {
		return;
	}
	this._lastReachableSystems = ids;
	var systems = [];
	for (var i = 0; i < nearby.length; i++) {
		var info = nearby[i];
		var distance = origin.distanceToSystem(info);
		var prices = {};
		for (var j = 0; j < commodities.length; j++) {
			var commodity = commodities[j];
			prices[commodity] = info.samplePrice(commodity);
		}
		systems.push({
			id: info.systemID,
			name: info.name,
			distance: distance,
			economy: info.economy,
			government: info.government,
			techLevel: info.techlevel,
			samplePrices: prices
		});
	}
	this._emit("systems", { fuel: fuel, systems: systems });
};

this._emitChartTarget = function () {
	this._emit("chart_target", {
		infoSystem: player.ship.infoSystem,
		targetSystem: player.ship.targetSystem
	});
};

// The station's "about to expire" switch to TIMING_OUT fires no script event
// (StationEntity update:), so check once a second while inside an aegis and
// report changes only.
this._watchClearance = function (on) {
	if (on && !this._clearanceTimer) {
		this._lastClearance = player.dockingClearanceStatus;
		this._clearanceTimer = new Timer(this, function () {
			if (player.dockingClearanceStatus !== this._lastClearance) {
				this._emitClearance("changed");
			}
		}, 1, 1);
	} else if (!on && this._clearanceTimer) {
		this._clearanceTimer.stop();
		this._clearanceTimer = null;
	}
};

/* Startup */

this.startUp = function () {
	this._lastReachableSystems = null;
	this._emit("hello", { version: this.version });
};

this.startUpComplete = function () {
	this._emit("ready", {
		docked: player.ship.docked,
		view: player.ship.viewDirection,
		alert: player.alertCondition
	});
	if (!player.ship.docked) {
		this._emitAegis(null);
	} else {
		this._emitMarket();
	}
	this._emitSystems();
	this._emitChartTarget();
};

/* Screens and views */

this.guiScreenChanged = function (to, from) {
	this._emit("gui", { to: to, from: from });
	if (to === "GUI_SCREEN_MARKET" && player.ship.docked) {
		this._emitMarket();
	}
};

// F1-F4 in flight: forward/aft/port/starboard. The GUI screen stays MAIN.
this.viewDirectionChanged = function (to, from) {
	this._emit("view", { to: to, from: from });
};

/* Docking and stations */

this.shipDockedWithStation = function (station) {
	this._watchClearance(false);
	this._emit("docked", { station: station.displayName });
	this._emitMarket(station);
	this._emitSystems();
};

this.shipWillLaunchFromStation = function (station) {
	this._emit("launching", { station: station.displayName });
};

this.shipLaunchedFromStation = function (station) {
	this._emitAegis(station);  // launching leaves you inside the aegis
};

this.shipEnteredStationAegis = function (station) {
	this._emitAegis(station);
};

this.shipExitedStationAegis = function (station) {
	this._emitAegis(null);
};

this.playerRequestedDockingClearance = function (message) {
	this._emitClearance("requested");
};

this.playerDockingClearanceGranted = function () {
	this._emitClearance("granted");
};

this.playerDockingClearanceExpired = function () {
	this._emitClearance("expired");
};

this.playerDockingClearanceCancelled = function () {
	this._emitClearance("cancelled");
};

this.playerDockingRefused = function (station) {
	this._emitClearance("refused");
};

this.playerBoughtCargo = function (commodity, units, price) {
	var data = this._marketLocation();
	data.commodity = commodity;
	data.units = units;
	data.price = price;
	this._emit("bought", data);
};

this.playerSoldCargo = function (commodity, units, price) {
	var data = this._marketLocation();
	data.commodity = commodity;
	data.units = units;
	data.price = price;
	this._emit("sold", data);
};

this.playerStartedAutoPilot = function (station) {
	this._emit("autopilot", { on: true });
};

this.playerCancelledAutoPilot = function () {
	this._emit("autopilot", { on: false });
};

/* Alert condition: 0 docked, 1 green, 2 yellow, 3 red */

this.alertConditionChanged = function (newCondition, oldCondition) {
	this._emit("alert", { level: newCondition });
};

/* Hyperspace and galactic jumps */

this.playerStartedJumpCountdown = function (type, seconds) {
	this._emit("countdown", { kind: type, seconds: seconds });
};

this.playerCancelledJumpCountdown = function () {
	this._emit("countdown_end", { reason: "cancelled" });
};

this.playerJumpFailed = function (reason) {
	this._emit("countdown_end", { reason: reason });
};

this.shipWillEnterWitchspace = function (cause) {
	this._emit("countdown_end", { reason: "jumped", cause: cause });
};

this.shipExitedWitchspace = function () {
	this._emit("arrived", { system: system.name, alert: player.alertCondition });
	this._emitAegis(null);
	this._emitSystems();
	this._emitChartTarget();
};

this.shipScoopedFuel = function () {
	this._emitSystems(true);
};

this.infoSystemChanged = function () {
	this._emitChartTarget();
};
