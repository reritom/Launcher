# Abstract

Consider a bot that given bot has 2 attributes. The average flight time (flight_time), and the average speed (speed). Trivially, we can assume that the average maximum distance the bot can travel is flight_time/speed.

For a given bot with a flight_time of 20 minutes, and a speed of 5 metres per second, we can assume the maximum distance 5*(20*60) = 6000 metres.

But what if you wish to fly the bot 10km? or 20km? What if you want to fly 10km and then maintain that position for an hour before returning 10km to the starting point? In these cases we have a clear energy deficit.

This project considers the scheduling of a dynamic in-flight refuelling system.

# Introduction
Introduction
terminology: flight plan, waypoint, tower, bot, scheduler


## Flight plans
Flight plans

mostly defined flight plan
```json
{
  "hello": "world"
}

```
json repr
partially defined


## Schedules
Schedules

### Example 1
demo showing multiple towers

### Example 2
demo showing bots refueling eachother
![Dynamic Demo](demo/demo_1.gif)

### Example 3
demo showing multiple main bots creating a grid in space

# Core Logic
Core logic
