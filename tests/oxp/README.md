# CtxKeys add-on tests

Run the add-on tests with Node.js 18 or newer; they use only Node's built-in
test runner and `vm` module:

```sh
node --test tests/oxp/
```

`fake-oolite.js` defines the Oolite properties used by the add-on in one place.
Its strict stubs throw if the script reads or writes an undeclared property,
helping catch binding-name typos without a running game. The tests manually
tick timers and check the exact JSON sent through both `log()` and
`debugConsole.consoleMessage()`.

The property stub cites the Oolite 1.92.1 JavaScript bindings inline:

- [`OOJSPlayer.m`](https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSPlayer.m)
- [`OOJSPlayerShip.m`](https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSPlayerShip.m)
- [`OOJSShip.m`](https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSShip.m)
- [`OOJSStation.m`](https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSStation.m)
