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
	}
};

/* Screens and views */

this.guiScreenChanged = function (to, from) {
	this._emit("gui", { to: to, from: from });
};

// F1-F4 in flight: forward/aft/port/starboard. The GUI screen stays MAIN.
this.viewDirectionChanged = function (to, from) {
	this._emit("view", { to: to, from: from });
};

/* Docking and stations */

this.shipDockedWithStation = function (station) {
	this._watchClearance(false);
	this._emit("docked", { station: station.displayName });
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
};
