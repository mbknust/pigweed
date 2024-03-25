// Copyright 2024 The Pigweed Authors
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may not
// use this file except in compliance with the License. You may obtain a copy of
// the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations under
// the License.

#include "pw_allocator/block_allocator.h"
#include "pw_allocator/metrics.h"
#include "pw_allocator/size_reporter.h"
#include "pw_allocator/tracking_allocator.h"

int main() {
  pw::allocator::SizeReporter reporter;
  reporter.SetBaseline();

  pw::allocator::FirstFitBlockAllocator<uint16_t> allocator(reporter.buffer());
  pw::allocator::TrackingAllocatorImpl<pw::allocator::NoMetrics> tracker(
      1, allocator);
  reporter.Measure(tracker);

  return 0;
}