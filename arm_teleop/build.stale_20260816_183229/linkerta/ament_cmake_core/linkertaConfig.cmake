# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_linkerta_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED linkerta_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(linkerta_FOUND FALSE)
  elseif(NOT linkerta_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(linkerta_FOUND FALSE)
  endif()
  return()
endif()
set(_linkerta_CONFIG_INCLUDED TRUE)

# output package information
if(NOT linkerta_FIND_QUIETLY)
  message(STATUS "Found linkerta: 0.0.1 (${linkerta_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'linkerta' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT ${linkerta_DEPRECATED_QUIET})
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(linkerta_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${linkerta_DIR}/${_extra}")
endforeach()
