"use strict";

this.name = "ctxkeys-test";
this.author = "Kieron";
this.version = "0.1";
this.description = "Test setup for the helper: contracts for the commander named Test.";

// Only the test commander (scripts/test-game.sh installs the save): anyone
// else's game is left alone.
var COMMANDER = "Test";

// Gives a passenger, a parcel and a cargo contract when docked at a main
// station, each kind only if none is aboard. These calls take the same path
// as accepting a job on the Interfaces screen (PlayerEntityContracts.m
// addPassenger:, addParcel:, awardContract:, 1.92.1), so playerEnteredContract
// fires for each. The ETA must be in the future; the parcel's is 2 minutes,
// so it's late soon after launch.
this._giveContracts = function () {
	var ship = player.ship;
	if (player.name !== COMMANDER || !ship.docked || ship.dockedStation !== system.mainStation) return;
	var near = system.info.systemsInRange(7);
	if (near.length < 2) return;
	var here = system.ID, first = near[0].systemID, second = near[1].systemID;
	var now = clock.seconds;
	// The standard Cobra III has no passenger berth (it takes 5 t of cargo space).
	if (!ship.passengerCapacity) ship.awardEquipment("EQ_PASSENGER_BERTH");
	if (!ship.passengers.length) ship.addPassenger("Test Passenger", here, first, now + 2 * 86400, 240);
	if (!ship.parcels.length) ship.addParcel("Test parcel", here, second, now + 120, 180);
	if (!ship.contracts.length) ship.awardContract(5, "furs", here, first, now + 3 * 86400, 900);
	log(this.name, "passengers " + ship.passengers.length + ", parcels " + ship.parcels.length +
		", contracts " + ship.contracts.length);
};

// A moment after loading, so the helper's add-on has sent the first hold.
this.startUpComplete = function () {
	this._timer = new Timer(this, this._giveContracts, 2);
};

this.shipDockedWithStation = function () {
	this._giveContracts();
};
