if mad has_command x; then
	start_test Deferred execution
	test_data 3
	mad x -s 'cat {{filename}} | cut -f 1 -d" "' a00?.test

	#run command - count number of output lines
	mad catchup *test | wc -l | grep -q 6

	#commands are removed after execution
	mad catchup *test | wc -l | grep -q 0
else
	skip_test
fi