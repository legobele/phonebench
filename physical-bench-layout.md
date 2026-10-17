# Physical Bench Layout — phonebench v0.1

Source: founder's top-down diagram, "phonebench v0.1 [TOOLS ARRANGEMENT]", shared October 15, 2026. This is the planned PHYSICAL setup (the sim is its rehearsal).

## Layout (top-down)

- **Center: the repair area.** The phone (green) sits on a **heatpad** (blue field) that does three jobs: heats (adhesive softening for opening), holds the phone, and **can rotate up to 180° to either side** — flipping the phone for front/back work without the arm re-gripping it.
- **Left column, tall zone: TOOLS.** Tool staging along the left edge.
- **Left column, below tools: SCREW HOLDING AREA.** Dedicated fastener organization zone, adjacent to tools — the physical home of the fastener-management discipline (every screw parked in its place).
- **Bottom center: ARM BASE.** The arm is based below the repair area, centered on it, reaching up into the phone zone with tools to its left.
- Diagram scale marker: 1 in.

## Variant: SW DIAG CONFIG (founder diagram, October 15, 2026)

Same bench in its software/diagnostic configuration:

- The heatpad gains a second motion: it can also tilt **upward while off** (presenting the phone at an angle, not just rotating flat).
- **MagSafe to phone**: a MagSafe connection powers/charges the phone on the pad.
- **USB-OTG OUT**: a wired out connection from the phone — the data/mirror link the display touch system works against.
- **Free area for display touch system**: a dedicated reserved zone below the phone on the pad side — the display touch hardware lives here, deliberately given its own real estate rather than squeezed into the tool column.
- Tilt spec from the follow-up diagram: the upward tilt goes to **70 degrees** while off.
- **No-MagSafe config** (third diagram, October 15, 2026): an extra configuration without the MagSafe connection — same SW DIAG layout otherwise; power/data ride the wired USB-OTG link only.

## Scale problem: the tablet configuration (founder, October 15, 2026)

The v0.1 bench is phone-scale. An 11-inch tablet (the iPad Pro 11" M1 is the first tablet-class device entering the benchmark) does not fit the phone fixture, heatpad, or cradle geometry. The bench needs a **bigger workbench** configuration for tablet-class devices:

- Same layout philosophy and zones (tools column, dedicated screw holding area, arm base centered on the work, reserved display-touch area, MagSafe/wired diag configs), scaled to a tablet footprint.
- The rotating/tilting heatpad fixture must hold an 11-inch device through the same motions (180° rotation, 70° tilt while off) without the device overhanging the pad.
- Sim implication: when the iPad is parameterized, the Bench/fixture layer needs a device size class (phone vs tablet), not a phone fixture with a bigger phone in it.

## Instrumentation (founder, October 15, 2026)

Temperature readers are fitted on EVERYTHING: every component of the bench and the device under repair carries a temp reader (device body and battery, arm segments/motors, power packs, compressor, heat plate, tools). If it exists and has a temperature, it has a reader.

## Tool interface (founder, October 15, 2026)

- Tools mount on a **standard adapter, drill-chuck style, but with power terminals on it**: the coupling is mechanical AND powered, so mounted tools are active instruments (the screwdriver is a powered driver, not a passive shaft).
- Tools are retained by a **combination of magnetic suction and air (vacuum) suction**: magnetic hold plus vacuum hold together, so a tool stays seated under load but can release fast for swaps.
- **Display touch tool:** a specialized tool that touches the display while the phone is connected to **screen mirroring** — the mirror is the agent's eyes on the screen, this tool is its finger (taps, swipes, unlock and activation flows).

## Design reads

- Rotation in the fixture, not the gripper: flipping is the highest-risk handling moment in a repair; putting the 180° turn in the heatpad removes it from the arm's job.
- Screw holding gets its own real estate, not a corner of the tool zone: fastener identity is a first-class concern of the bench, same as in the sim's spec.
- Everything the arm needs is within one reach envelope: phone center, tools left, screws left, base bottom-center.
