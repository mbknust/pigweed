// Copyright 2023 The Pigweed Authors
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

#include "pw_containers/variable_length_entry_deque.h"

#include <cstring>
#include <string_view>
#include <variant>

#include "gtest/gtest.h"
#include "pw_containers_private/variable_length_entry_deque_test_oracle.h"

namespace {

using std::string_view_literals::operator""sv;

struct PushOverwrite {
  std::string_view data;
};
struct Push {
  std::string_view data;
};
struct Pop {};
struct SizeEquals {
  size_t expected;
};

using TestStep = std::variant<PushOverwrite, Push, Pop, SizeEquals>;

// Copies an entry, which might be wrapped, to a single std::vector.
std::vector<std::byte> ReadEntry(
    const pw_VariableLengthEntryDeque_Iterator& it) {
  auto entry = pw_VariableLengthEntryDeque_GetEntry(&it);
  std::vector<std::byte> value(entry.size_1 + entry.size_2);
  EXPECT_EQ(value.size(),
            pw_VariableLengthEntryDeque_Entry_Copy(
                &entry, value.data(), entry.size_1 + entry.size_2));
  return value;
}

#define ASSERT_CONTENTS_EQ(oracle, deque)                                      \
  auto oracle_it = oracle.begin();                                             \
  auto deque_it = pw_VariableLengthEntryDeque_Begin(deque);                    \
  const auto deque_end = pw_VariableLengthEntryDeque_End(deque);               \
  uint32_t entries_compared = 0;                                               \
  while (oracle_it != oracle.end() &&                                          \
         !pw_VariableLengthEntryDeque_Iterator_Equal(&deque_it, &deque_end)) { \
    ASSERT_EQ(*oracle_it++, ReadEntry(deque_it));                              \
    pw_VariableLengthEntryDeque_Iterator_Advance(&deque_it);                   \
    entries_compared += 1;                                                     \
  }                                                                            \
  ASSERT_EQ(entries_compared, oracle.size())

// Declares a test that performs a series of operations on a
// VariableLengthEntryDeque and the "oracle" class, and checks that they match
// after every step.
#define DATA_DRIVEN_TEST(program, max_entry_size)                              \
  TEST(VariableLengthEntryDeque,                                               \
       DataDrivenTest_##program##_MaxEntrySize##max_entry_size) {              \
    pw::containers::VariableLengthEntryDequeTestOracle oracle(max_entry_size); \
    PW_VARIABLE_LENGTH_ENTRY_DEQUE_DECLARE(c_deque, max_entry_size);           \
                                                                               \
    for (const TestStep& step : program) {                                     \
      /* Take the action */                                                    \
      if (auto ow = std::get_if<PushOverwrite>(&step); ow != nullptr) {        \
        pw_VariableLengthEntryDeque_PushBackOverwrite(                         \
            c_deque, ow->data.data(), static_cast<uint32_t>(ow->data.size())); \
        oracle.push_back_overwrite(pw::as_bytes(pw::span(ow->data)));          \
      } else if (auto push = std::get_if<Push>(&step); push != nullptr) {      \
        pw_VariableLengthEntryDeque_PushBack(                                  \
            c_deque,                                                           \
            push->data.data(),                                                 \
            static_cast<uint32_t>(push->data.size()));                         \
        oracle.push_back(pw::as_bytes(pw::span(push->data)));                  \
      } else if (auto pop = std::get_if<Pop>(&step); pop != nullptr) {         \
        pw_VariableLengthEntryDeque_PopFront(c_deque);                         \
        oracle.pop_front();                                                    \
      } else if (auto size = std::get_if<SizeEquals>(&step);                   \
                 size != nullptr) {                                            \
        size_t actual = pw_VariableLengthEntryDeque_Size(c_deque);             \
        ASSERT_EQ(oracle.size(), actual);                                      \
        ASSERT_EQ(size->expected, actual);                                     \
      } else {                                                                 \
        FAIL() << "Unhandled case";                                            \
      }                                                                        \
      /* Check size and other functions */                                     \
      ASSERT_EQ(pw_VariableLengthEntryDeque_Size(c_deque), oracle.size());     \
      ASSERT_EQ(pw_VariableLengthEntryDeque_RawSizeBytes(c_deque),             \
                oracle.raw_size_bytes());                                      \
      ASSERT_EQ(pw_VariableLengthEntryDeque_RawCapacityBytes(c_deque),         \
                oracle.raw_capacity_bytes());                                  \
      ASSERT_EQ(pw_VariableLengthEntryDeque_MaxEntrySizeBytes(c_deque),        \
                oracle.max_entry_size_bytes());                                \
      ASSERT_CONTENTS_EQ(oracle, c_deque);                                     \
    }                                                                          \
  }                                                                            \
  static_assert(true, "use a semicolon")

constexpr TestStep kPop[] = {
    SizeEquals{0},
    PushOverwrite{""sv},
    SizeEquals{1},
    Pop{},
    SizeEquals{0},
};

DATA_DRIVEN_TEST(kPop, 1);
DATA_DRIVEN_TEST(kPop, 6);

constexpr TestStep kOverwriteLargeEntriesWithSmall[] = {
    TestStep{PushOverwrite{"12345"sv}},  // 6-byte entry
    TestStep{PushOverwrite{"abcde"sv}},
    TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{""sv}},
    TestStep{SizeEquals{6}},
    TestStep{Pop{}},
    TestStep{Pop{}},
    TestStep{Pop{}},
    TestStep{Pop{}},
    TestStep{Pop{}},
    TestStep{Pop{}},
    TestStep{SizeEquals{0}},
};
DATA_DRIVEN_TEST(kOverwriteLargeEntriesWithSmall, 6);
DATA_DRIVEN_TEST(kOverwriteLargeEntriesWithSmall, 7);

constexpr TestStep kOverwriteVaryingSizesUpTo3[] = {
    TestStep{PushOverwrite{""sv}},   TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{""sv}},   TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{""sv}},   TestStep{PushOverwrite{"1"sv}},
    TestStep{PushOverwrite{"2"sv}},  TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{"3"sv}},  TestStep{PushOverwrite{"4"sv}},
    TestStep{PushOverwrite{""sv}},   TestStep{PushOverwrite{"5"sv}},
    TestStep{PushOverwrite{"6"sv}},  TestStep{PushOverwrite{"ab"sv}},
    TestStep{PushOverwrite{"cd"sv}}, TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{"ef"sv}}, TestStep{PushOverwrite{"gh"sv}},
    TestStep{PushOverwrite{"ij"sv}},
};
DATA_DRIVEN_TEST(kOverwriteVaryingSizesUpTo3, 3);
DATA_DRIVEN_TEST(kOverwriteVaryingSizesUpTo3, 4);

constexpr TestStep kOverwriteVaryingSizesUpTo5[] = {
    TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{""sv}},
    TestStep{PushOverwrite{"1"sv}},
    TestStep{PushOverwrite{"2"sv}},
    TestStep{PushOverwrite{"3"sv}},
    TestStep{PushOverwrite{"ab"sv}},
    TestStep{PushOverwrite{"cd"sv}},
    TestStep{PushOverwrite{"ef"sv}},
    TestStep{PushOverwrite{"123"sv}},
    TestStep{PushOverwrite{"456"sv}},
    TestStep{PushOverwrite{"789"sv}},
    TestStep{PushOverwrite{"abcd"sv}},
    TestStep{PushOverwrite{"efgh"sv}},
    TestStep{PushOverwrite{"ijkl"sv}},
    TestStep{Pop{}},
    TestStep{SizeEquals{0}},
};
DATA_DRIVEN_TEST(kOverwriteVaryingSizesUpTo5, 5);
DATA_DRIVEN_TEST(kOverwriteVaryingSizesUpTo5, 6);
DATA_DRIVEN_TEST(kOverwriteVaryingSizesUpTo5, 7);

constexpr char kBigEntryBytes[196]{};

constexpr TestStep kTwoBytePrefix[] = {
    TestStep{PushOverwrite{std::string_view(kBigEntryBytes, 128)}},
    TestStep{PushOverwrite{std::string_view(kBigEntryBytes, 128)}},
    TestStep{PushOverwrite{std::string_view(kBigEntryBytes, 127)}},
    TestStep{PushOverwrite{std::string_view(kBigEntryBytes, 128)}},
    TestStep{PushOverwrite{std::string_view(kBigEntryBytes, 127)}},
};
DATA_DRIVEN_TEST(kTwoBytePrefix, 130);

TEST(VariableLengthEntryDeque, DeclareMacro) {
  PW_VARIABLE_LENGTH_ENTRY_DEQUE_DECLARE(deque, 123);

  constexpr size_t kArraySizeBytes =
      123 + 1 /*prefix*/ + 1 /* end */ + 3 /* round up */ +
      PW_VARIABLE_LENGTH_ENTRY_DEQUE_HEADER_SIZE_UINT32 * 4;
  static_assert(sizeof(deque) == kArraySizeBytes);
  EXPECT_EQ(pw_VariableLengthEntryDeque_RawStorageSizeBytes(deque),
            kArraySizeBytes - 3 /* padding isn't included */);

  EXPECT_EQ(pw_VariableLengthEntryDeque_MaxEntrySizeBytes(deque), 123u);
  EXPECT_EQ(pw_VariableLengthEntryDeque_RawSizeBytes(deque), 0u);
  EXPECT_TRUE(pw_VariableLengthEntryDeque_Empty(deque));
}

TEST(VariableLengthEntryDeque, InitializeExistingBuffer) {
  constexpr size_t kArraySize =
      10 + PW_VARIABLE_LENGTH_ENTRY_DEQUE_HEADER_SIZE_UINT32;
  uint32_t deque[kArraySize];
  pw_VariableLengthEntryDeque_Init(deque, kArraySize);

  EXPECT_EQ(pw_VariableLengthEntryDeque_RawStorageSizeBytes(deque),
            sizeof(deque));
  EXPECT_EQ(pw_VariableLengthEntryDeque_MaxEntrySizeBytes(deque),
            sizeof(uint32_t) * 10u - 1 /*prefix*/ - 1 /*end*/);
  EXPECT_EQ(pw_VariableLengthEntryDeque_RawSizeBytes(deque), 0u);
  EXPECT_EQ(pw_VariableLengthEntryDeque_Size(deque), 0u);
  EXPECT_TRUE(pw_VariableLengthEntryDeque_Empty(deque));
}

TEST(VariableLengthEntryDeque, MaxSizeElement) {
  // Test max size elements for a few sizes. Commented out statements fail an
  // assert because the elements are too large.
  PW_VARIABLE_LENGTH_ENTRY_DEQUE_DECLARE(dq16, 126);
  PW_VARIABLE_LENGTH_ENTRY_DEQUE_DECLARE(dq17, 127);
  PW_VARIABLE_LENGTH_ENTRY_DEQUE_DECLARE(dq18, 128);
  PW_VARIABLE_LENGTH_ENTRY_DEQUE_DECLARE(dq19, 129);

  pw_VariableLengthEntryDeque_PushBackOverwrite(dq16, kBigEntryBytes, 126);
  pw_VariableLengthEntryDeque_PushBackOverwrite(dq17, kBigEntryBytes, 126);
  pw_VariableLengthEntryDeque_PushBackOverwrite(dq18, kBigEntryBytes, 126);
  pw_VariableLengthEntryDeque_PushBackOverwrite(dq19, kBigEntryBytes, 126);

  // pw_VariableLengthEntryDeque_PushBackOverwrite(dq16, kBigEntryBytes, 127);
  pw_VariableLengthEntryDeque_PushBackOverwrite(dq17, kBigEntryBytes, 127);
  pw_VariableLengthEntryDeque_PushBackOverwrite(dq18, kBigEntryBytes, 127);
  pw_VariableLengthEntryDeque_PushBackOverwrite(dq19, kBigEntryBytes, 127);

  // pw_VariableLengthEntryDeque_PushBackOverwrite(dq16, kBigEntryBytes, 128);
  // pw_VariableLengthEntryDeque_PushBackOverwrite(dq17, kBigEntryBytes, 128);
  pw_VariableLengthEntryDeque_PushBackOverwrite(dq18, kBigEntryBytes, 128);
  pw_VariableLengthEntryDeque_PushBackOverwrite(dq19, kBigEntryBytes, 128);

  // pw_VariableLengthEntryDeque_PushBackOverwrite(dq16, kBigEntryBytes, 129);
  // pw_VariableLengthEntryDeque_PushBackOverwrite(dq17, kBigEntryBytes, 129);
  // pw_VariableLengthEntryDeque_PushBackOverwrite(dq18, kBigEntryBytes, 129);
  pw_VariableLengthEntryDeque_PushBackOverwrite(dq19, kBigEntryBytes, 129);

  EXPECT_EQ(pw_VariableLengthEntryDeque_Size(dq16), 1u);
  EXPECT_EQ(pw_VariableLengthEntryDeque_Size(dq17), 1u);
  EXPECT_EQ(pw_VariableLengthEntryDeque_Size(dq18), 1u);
  EXPECT_EQ(pw_VariableLengthEntryDeque_Size(dq19), 1u);
}

}  // namespace
