import unittest, datetime

from .resource_allocator import ResourceAllocator, AllocationError, Resource


class TestResourceAllocator(unittest.TestCase):
    def test_add_resource(self):
        resource = Resource(id="id1")
        manager = ResourceAllocator(reference="Test", resources=[resource])

        # Test 1
        resource_2 = Resource(id="id2")
        manager.add_resource(resource_2)
        self.assertTrue(resource_2.id in manager.allocator)

        # Test 2 - This will raise an exception because a resource with this id already exists
        with self.assertRaises(AllocationError) as ctx:
            manager.add_resource(resource)

    def test_allocate_resource(self):
        resource_1 = Resource(id="id1")
        resource_2 = Resource(id="id2")
        manager = ResourceAllocator(reference="Test", resources=[resource_1, resource_2])

        # Test 1
        manager.allocate_resource(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 12, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 13, 0, 0)
        )

        # Test 2 - Allocating another resource at the same time
        manager.allocate_resource(
            resource_id="id2",
            from_datetime=datetime.datetime(2010, 5, 5, 12, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 13, 0, 0)
        )

        # Test 3 - Trying make an overlapping allocation will cause an exception
        with self.assertRaises(AllocationError) as ctx:
            manager.allocate_resource(
                resource_id="id1",
                from_datetime=datetime.datetime(2010, 5, 5, 12, 45, 0),
                to_datetime=datetime.datetime(2010, 5, 5, 13, 45, 0)
            )

    def test_get_allocations(self):
        # Test 1 - Nothing for this resource
        manager = ResourceAllocator(reference="Test")
        allocation = manager.get_allocations(resource_id="id1")
        self.assertIsNone(allocation)

        # Test 2
        resource_1 = Resource(id="id1")
        manager = ResourceAllocator(reference="Test", resources=[resource_1])

        manager.allocate_resource(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 12, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 13, 0, 0)
        )
        manager.allocate_resource(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 13, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 14, 0, 0)
        )

        allocations = manager.get_allocations(resource_id="id1")
        self.assertEqual(2, len(allocations))

    def test_get_allocation_by_time(self):
        resource_1 = Resource(id="id1")
        manager = ResourceAllocator(reference="Test", resources=[resource_1])

        manager.allocate_resource(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 12, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 13, 0, 0)
        )
        manager.allocate_resource(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 13, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 14, 0, 0)
        )

        # Test 1 - No allocations at this time
        allocation = manager.get_allocation_by_time(resource_id="id1", allocation_time=datetime.datetime(2010, 5, 5, 15, 30, 0))
        self.assertIsNone(allocation)

        # Test 2
        allocation = manager.get_allocation_by_time(resource_id="id1", allocation_time=datetime.datetime(2010, 5, 5, 12, 30, 0))
        self.assertIsNotNone(allocation)

    def test_get_allocation_by_id(self):
        resource_1 = Resource(id="id1")
        manager = ResourceAllocator(reference="Test", resources=[resource_1])

        manager.allocate_resource(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 12, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 13, 0, 0)
        )
        manager.allocate_resource(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 13, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 14, 0, 0)
        )

        # Test 1 - No allocations with this id
        allocation = manager.get_allocation_by_id(allocation_id="non-existant-id")
        self.assertIsNone(allocation)

        # Test 2
        allocation = manager.allocator["id1"][-1]
        retrieved_allocation = manager.get_allocation_by_id(allocation_id=allocation.id)
        self.assertEqual(allocation, retrieved_allocation)

    def test_delete_allocation(self):
        resource_1 = Resource(id="id1")
        manager = ResourceAllocator(reference="Test", resources=[resource_1])

        # Test 1 - Nothing to delete
        self.assertIsNone(manager.delete_allocation(allocation_id="non-existant-id"))

        # Test 2 - Something to delete
        allocation_id = manager.allocate_resource(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 12, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 13, 0, 0)
        )
        self.assertEqual(1, len(manager.allocator["id1"]))
        manager.delete_allocation(allocation_id)
        self.assertEqual(0, len(manager.allocator["id1"]))


    def test_is_allocation_available(self):
        resource_1 = Resource(id="id1")
        manager = ResourceAllocator(reference="Test", resources=[resource_1])

        # Test 1 - Allocation is available
        is_available = manager.is_allocation_available(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 12, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 13, 0, 0)
        )
        self.assertTrue(is_available)

        # Test 2 - Allocation isnt available
        manager.allocate_resource(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 12, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 13, 0, 0)
        )

        is_available = manager.is_allocation_available(
            resource_id="id1",
            from_datetime=datetime.datetime(2010, 5, 5, 12, 30, 0),
            to_datetime=datetime.datetime(2010, 5, 5, 13, 0, 0)
        )
        self.assertFalse(is_available)
        self.assertTrue(len(manager.allocator["id1"]) == 1)
