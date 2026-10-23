cmake_minimum_required(VERSION 3.20)
project(MonsterPartyRecomp VERSION 0.1.1 LANGUAGES C CXX)
set(NESRECOMP_GAME_VERSION "${PROJECT_VERSION}" CACHE STRING "Game release version")
set(NESRECOMP_BACKEND "cycle" CACHE STRING "Execution backend (cycle only)")
if(NOT NESRECOMP_BACKEND STREQUAL "cycle")
    message(FATAL_ERROR "Monster Party uses the cycle backend")
endif()

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

set(NESRECOMP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/nesrecomp" CACHE PATH "NESRecomp engine checkout")

# nesrecomp/ and recomp-ui/ are git submodules (see .gitmodules); run
# `git submodule update --init --recursive` after cloning.

set(NESRECOMP_ROM "" CACHE FILEPATH "Original Monster Party (USA) ROM image, not distributed")
set(NESRECOMP_CYCLE_SEEDS "${CMAKE_CURRENT_SOURCE_DIR}/cyc_seeds.txt" CACHE FILEPATH "Cycle coverage seeds")
set(NESRECOMP_HOST_COMPILER "" CACHE FILEPATH "Optional prebuilt host NESRecomp compiler")
if(NOT EXISTS "${NESRECOMP_ROM}")
    message(FATAL_ERROR "Set NESRECOMP_ROM to the original Monster Party (USA) ROM")
endif()
find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/verify_usa_rom.py"
    --rom "${NESRECOMP_ROM}" --crc 02B9E7C2 --mapper 1 --title "Monster Party"
    RESULT_VARIABLE _usa_rom_result)
if(NOT _usa_rom_result EQUAL 0)
    message(FATAL_ERROR "The North American ROM profile is required for this build")
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/verify_usa_rom.py" "${NESRECOMP_ROM}")

if(UNIX AND NOT APPLE AND NOT NESRECOMP_HEADLESS)
    find_package(SDL2 2.24 REQUIRED CONFIG)
endif()
include("${NESRECOMP_ROOT}/runner/cyc/project.cmake")
nesrecomp_add_cycle_game(MonsterPartyRecomp
    ROM "${NESRECOMP_ROM}"
    GAME_CONFIG "${CMAKE_CURRENT_SOURCE_DIR}/game.toml"
    RECOMPILER "${NESRECOMP_HOST_COMPILER}"
    SEED_FILE "${NESRECOMP_CYCLE_SEEDS}"
    MODS GAME_ID "monster-party-usa"
    HOST_EXTRAS src/mp_host.c src/mp_assist.c src/mp_widescreen.c
    BOXART "${CMAKE_CURRENT_SOURCE_DIR}/assets/boxart.tga"
    PLAYERS 1 REGION NTSC)
target_include_directories(MonsterPartyRecomp PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
add_custom_command(TARGET MonsterPartyRecomp POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CMAKE_CURRENT_SOURCE_DIR}/mods/preloaded" "$<TARGET_FILE_DIR:MonsterPartyRecomp>/mods")
