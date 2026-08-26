// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from lbot_arm_interfaces:srv/GetFrame.idl
// generated code does not contain a copyright notice
#include "lbot_arm_interfaces/srv/detail/get_frame__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"

// Include directives for member types
// Member `name`
#include "rosidl_runtime_c/string_functions.h"

bool
lbot_arm_interfaces__srv__GetFrame_Request__init(lbot_arm_interfaces__srv__GetFrame_Request * msg)
{
  if (!msg) {
    return false;
  }
  // name
  if (!rosidl_runtime_c__String__init(&msg->name)) {
    lbot_arm_interfaces__srv__GetFrame_Request__fini(msg);
    return false;
  }
  return true;
}

void
lbot_arm_interfaces__srv__GetFrame_Request__fini(lbot_arm_interfaces__srv__GetFrame_Request * msg)
{
  if (!msg) {
    return;
  }
  // name
  rosidl_runtime_c__String__fini(&msg->name);
}

bool
lbot_arm_interfaces__srv__GetFrame_Request__are_equal(const lbot_arm_interfaces__srv__GetFrame_Request * lhs, const lbot_arm_interfaces__srv__GetFrame_Request * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // name
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->name), &(rhs->name)))
  {
    return false;
  }
  return true;
}

bool
lbot_arm_interfaces__srv__GetFrame_Request__copy(
  const lbot_arm_interfaces__srv__GetFrame_Request * input,
  lbot_arm_interfaces__srv__GetFrame_Request * output)
{
  if (!input || !output) {
    return false;
  }
  // name
  if (!rosidl_runtime_c__String__copy(
      &(input->name), &(output->name)))
  {
    return false;
  }
  return true;
}

lbot_arm_interfaces__srv__GetFrame_Request *
lbot_arm_interfaces__srv__GetFrame_Request__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  lbot_arm_interfaces__srv__GetFrame_Request * msg = (lbot_arm_interfaces__srv__GetFrame_Request *)allocator.allocate(sizeof(lbot_arm_interfaces__srv__GetFrame_Request), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(lbot_arm_interfaces__srv__GetFrame_Request));
  bool success = lbot_arm_interfaces__srv__GetFrame_Request__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
lbot_arm_interfaces__srv__GetFrame_Request__destroy(lbot_arm_interfaces__srv__GetFrame_Request * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    lbot_arm_interfaces__srv__GetFrame_Request__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
lbot_arm_interfaces__srv__GetFrame_Request__Sequence__init(lbot_arm_interfaces__srv__GetFrame_Request__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  lbot_arm_interfaces__srv__GetFrame_Request * data = NULL;

  if (size) {
    data = (lbot_arm_interfaces__srv__GetFrame_Request *)allocator.zero_allocate(size, sizeof(lbot_arm_interfaces__srv__GetFrame_Request), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = lbot_arm_interfaces__srv__GetFrame_Request__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        lbot_arm_interfaces__srv__GetFrame_Request__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
lbot_arm_interfaces__srv__GetFrame_Request__Sequence__fini(lbot_arm_interfaces__srv__GetFrame_Request__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      lbot_arm_interfaces__srv__GetFrame_Request__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

lbot_arm_interfaces__srv__GetFrame_Request__Sequence *
lbot_arm_interfaces__srv__GetFrame_Request__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  lbot_arm_interfaces__srv__GetFrame_Request__Sequence * array = (lbot_arm_interfaces__srv__GetFrame_Request__Sequence *)allocator.allocate(sizeof(lbot_arm_interfaces__srv__GetFrame_Request__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = lbot_arm_interfaces__srv__GetFrame_Request__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
lbot_arm_interfaces__srv__GetFrame_Request__Sequence__destroy(lbot_arm_interfaces__srv__GetFrame_Request__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    lbot_arm_interfaces__srv__GetFrame_Request__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
lbot_arm_interfaces__srv__GetFrame_Request__Sequence__are_equal(const lbot_arm_interfaces__srv__GetFrame_Request__Sequence * lhs, const lbot_arm_interfaces__srv__GetFrame_Request__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!lbot_arm_interfaces__srv__GetFrame_Request__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
lbot_arm_interfaces__srv__GetFrame_Request__Sequence__copy(
  const lbot_arm_interfaces__srv__GetFrame_Request__Sequence * input,
  lbot_arm_interfaces__srv__GetFrame_Request__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(lbot_arm_interfaces__srv__GetFrame_Request);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    lbot_arm_interfaces__srv__GetFrame_Request * data =
      (lbot_arm_interfaces__srv__GetFrame_Request *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!lbot_arm_interfaces__srv__GetFrame_Request__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          lbot_arm_interfaces__srv__GetFrame_Request__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!lbot_arm_interfaces__srv__GetFrame_Request__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `frame`
#include "lbot_arm_interfaces/msg/detail/lbot_frame__functions.h"

bool
lbot_arm_interfaces__srv__GetFrame_Response__init(lbot_arm_interfaces__srv__GetFrame_Response * msg)
{
  if (!msg) {
    return false;
  }
  // frame
  if (!lbot_arm_interfaces__msg__LbotFrame__init(&msg->frame)) {
    lbot_arm_interfaces__srv__GetFrame_Response__fini(msg);
    return false;
  }
  // success
  return true;
}

void
lbot_arm_interfaces__srv__GetFrame_Response__fini(lbot_arm_interfaces__srv__GetFrame_Response * msg)
{
  if (!msg) {
    return;
  }
  // frame
  lbot_arm_interfaces__msg__LbotFrame__fini(&msg->frame);
  // success
}

bool
lbot_arm_interfaces__srv__GetFrame_Response__are_equal(const lbot_arm_interfaces__srv__GetFrame_Response * lhs, const lbot_arm_interfaces__srv__GetFrame_Response * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // frame
  if (!lbot_arm_interfaces__msg__LbotFrame__are_equal(
      &(lhs->frame), &(rhs->frame)))
  {
    return false;
  }
  // success
  if (lhs->success != rhs->success) {
    return false;
  }
  return true;
}

bool
lbot_arm_interfaces__srv__GetFrame_Response__copy(
  const lbot_arm_interfaces__srv__GetFrame_Response * input,
  lbot_arm_interfaces__srv__GetFrame_Response * output)
{
  if (!input || !output) {
    return false;
  }
  // frame
  if (!lbot_arm_interfaces__msg__LbotFrame__copy(
      &(input->frame), &(output->frame)))
  {
    return false;
  }
  // success
  output->success = input->success;
  return true;
}

lbot_arm_interfaces__srv__GetFrame_Response *
lbot_arm_interfaces__srv__GetFrame_Response__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  lbot_arm_interfaces__srv__GetFrame_Response * msg = (lbot_arm_interfaces__srv__GetFrame_Response *)allocator.allocate(sizeof(lbot_arm_interfaces__srv__GetFrame_Response), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(lbot_arm_interfaces__srv__GetFrame_Response));
  bool success = lbot_arm_interfaces__srv__GetFrame_Response__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
lbot_arm_interfaces__srv__GetFrame_Response__destroy(lbot_arm_interfaces__srv__GetFrame_Response * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    lbot_arm_interfaces__srv__GetFrame_Response__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
lbot_arm_interfaces__srv__GetFrame_Response__Sequence__init(lbot_arm_interfaces__srv__GetFrame_Response__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  lbot_arm_interfaces__srv__GetFrame_Response * data = NULL;

  if (size) {
    data = (lbot_arm_interfaces__srv__GetFrame_Response *)allocator.zero_allocate(size, sizeof(lbot_arm_interfaces__srv__GetFrame_Response), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = lbot_arm_interfaces__srv__GetFrame_Response__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        lbot_arm_interfaces__srv__GetFrame_Response__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
lbot_arm_interfaces__srv__GetFrame_Response__Sequence__fini(lbot_arm_interfaces__srv__GetFrame_Response__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      lbot_arm_interfaces__srv__GetFrame_Response__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

lbot_arm_interfaces__srv__GetFrame_Response__Sequence *
lbot_arm_interfaces__srv__GetFrame_Response__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  lbot_arm_interfaces__srv__GetFrame_Response__Sequence * array = (lbot_arm_interfaces__srv__GetFrame_Response__Sequence *)allocator.allocate(sizeof(lbot_arm_interfaces__srv__GetFrame_Response__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = lbot_arm_interfaces__srv__GetFrame_Response__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
lbot_arm_interfaces__srv__GetFrame_Response__Sequence__destroy(lbot_arm_interfaces__srv__GetFrame_Response__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    lbot_arm_interfaces__srv__GetFrame_Response__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
lbot_arm_interfaces__srv__GetFrame_Response__Sequence__are_equal(const lbot_arm_interfaces__srv__GetFrame_Response__Sequence * lhs, const lbot_arm_interfaces__srv__GetFrame_Response__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!lbot_arm_interfaces__srv__GetFrame_Response__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
lbot_arm_interfaces__srv__GetFrame_Response__Sequence__copy(
  const lbot_arm_interfaces__srv__GetFrame_Response__Sequence * input,
  lbot_arm_interfaces__srv__GetFrame_Response__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(lbot_arm_interfaces__srv__GetFrame_Response);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    lbot_arm_interfaces__srv__GetFrame_Response * data =
      (lbot_arm_interfaces__srv__GetFrame_Response *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!lbot_arm_interfaces__srv__GetFrame_Response__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          lbot_arm_interfaces__srv__GetFrame_Response__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!lbot_arm_interfaces__srv__GetFrame_Response__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
